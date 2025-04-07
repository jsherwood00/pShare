import grpc
from concurrent import futures
import storage_node_pb2
import storage_node_pb2_grpc
import time
import os
import json
import random
from typing import List, Dict, Set, Tuple
import uuid_utils
import network_utils
import socket
import threading
from zeroconf import ServiceInfo, Zeroconf
from pathlib import Path
import uuid
import sys
import logging
#import google_util
#import aws_util

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
NODES_FILE = Path("storage_conf/nodes.json")

class StorageService(storage_node_pb2_grpc.StorageServiceServicer):
    def __init__(self):
        self.connected_clients: Dict[str, str] = {} # Clients: {UUID, IP:Port}
        self.client_contexts: Dict[str, grpc.ServicerContext] = {} # Store specific gRPC stuff needed for each client as each client has specific gRPC handling
        self.client_last_heartbeat: Dict[str, float] = {}  # Add timestamp tracking: {UUID: timestamp}
        self.client_file_ports: Dict[str, int] = {} # {UUID: port}
        self.client_storage_capacity: Dict[str, int] = {} # Client {UUID : storage_capacity}
        self.client_hostnames: Dict[str, str] = {} # {UUID: hostname}
        self.download_dir = "downloaded_files"
        os.makedirs(self.download_dir, exist_ok=True)
        self.nodes = self.load_nodes()  # Load nodes from file
        self.pending_nodes: Dict[str, str] = {}  # {UUID: address}
        self.pending_hostnames: Dict[str, str] = {} # For pending snodes: {UUID: hostname}
        self.pending_storage: Dict[str, str] = {} # For pending snodes: {UUID: tribute storage}

        # Start heartbeat monitoring thread
        self._start_heartbeat_monitor()

    # Check on clients every 5 secs
    def _start_heartbeat_monitor(self):
        """Remove clients who haven't sent a signal in the last 15 seconds"""
        def monitor_heartbeats():
            while True:
                current_time = time.time()
                ianctive_clients = []
                # Check for clients that haven't sent a heartbeat in 15 seconds
                for uuid, last_time in self.client_last_heartbeat.items():
                    if current_time - last_time > 15:  # 15 second timeout
                        ianctive_clients.append(uuid)
                # Remove inactive clients
                for uuid in ianctive_clients:
                    self._handle_client_disconnect(uuid)
                time.sleep(5)  # Check every 5 seconds

        
        # Do this in a non-blocking thread
        threading.Thread(target=monitor_heartbeats, daemon=True).start()

    def _handle_client_disconnect(self, uuid: str) -> None:
        """Remove client information when it disconnects"""
        if uuid in self.connected_clients:
            addr = self.connected_clients[uuid]
            logging.info(f"\nClient disconnected - UUID: {uuid}, Address: {addr}")
            del self.connected_clients[uuid]
            self.client_contexts.pop(uuid, None)
            self.client_last_heartbeat.pop(uuid, None)
            self.client_file_ports.pop(uuid, None)
            self.client_storage_capacity.pop(uuid, None)
            self.client_hostnames.pop(uuid, None)
        
        if uuid in self.pending_nodes:
            print(f"[DEBUG] processing disconnect for {uuid}")
            del self.pending_nodes[uuid]
            self.pending_hostnames.pop(uuid, None)
            self.pending_storage.pop(uuid, None)

    def load_nodes(self):
        """Load registered nodes from nodes.json."""
        NODES_FILE.parent.mkdir(parents=True, exist_ok=True)  # Create the directory if it doesn't exist
        if not NODES_FILE.exists():
            with NODES_FILE.open('w') as f:
                json.dump({}, f, indent=4)
        try:
            with NODES_FILE.open('r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}


    """ Changes state of a pending node to a connected snode """
    """ transfers data from pending dics to connected client
        dics, then saves as an snode in the json reference file,
        then removes its data from the pending dics """
    def save_node(self, uuid: str, node_type: str):
        """Save a selected node (RNODE or SNODE) to nodes.json."""
        self.nodes[uuid] = node_type
        self.client_storage_capacity[uuid] = self.pending_storage[uuid]
        self.client_hostnames[uuid] = self.pending_hostnames[uuid]
        
        # Remains connected for 15 additional seconds (prevents the delay
        # of waiting for the snode to send another request in order
        # for the frontend connected snodes to be updated)
        self.connected_clients[uuid] = uuid

        with NODES_FILE.open('w') as f:
            json.dump(self.nodes, f, indent=4)
        
        del self.pending_storage[uuid]
        del self.pending_hostnames[uuid]
        del self.pending_nodes[uuid]
        



    def Heartbeat(self, request_iterator, context):
        """Handle heartbeats from clients"""
        client_uuid = None
        
        try:
            for request in request_iterator:
                client_uuid = request.uuid
    
                if client_uuid not in self.connected_clients:

                    yield storage_node_pb2.HeartbeatResponse(
                        success=False,
                        message="Unknown client UUID"
                    )
                    return
                
                # Update last heartbeat timestamp
                self.client_last_heartbeat[client_uuid] = time.time()
                self.client_contexts[client_uuid] = context
                # Store specific file service port
                self.client_file_ports[client_uuid] = request.file_service_port
                # Store client committed storage
                self.client_storage_capacity[client_uuid] = request.storage_capacity_mb
                
                # Store host name
                # self.client_hostnames[client_uuid] = request.hostname
                # currently hostname the snode passes = instance name provided, or hostname by default
                self.client_hostnames[client_uuid] = request.hostname 
                yield storage_node_pb2.HeartbeatResponse(
                    success=True,
                    message="Heartbeat acknowledged"
                )
        except Exception as e:
            logging.error(f"Heartbeat error for client {client_uuid}: {e}", exc_info=True)
        finally:
            if client_uuid:
                self._handle_client_disconnect(client_uuid)


    def RequestUUID(self, request, context):
        """Hanlde when a client requests a UUID (first connection)"""
        try:
            if request.type == 'request_uuid':
            # Generate UUID for client and store it 
                temp_uuid = uuid_utils.generate_uuid()

                # old UUID handling code w/o approval from rnode
                """self.nodes[temp_uuid] = request.node_type
                self.save_node(temp_uuid, request.node_type)
                client_addr = context.peer()
                self.connected_clients[temp_uuid] = client_addr
                self.client_last_heartbeat[temp_uuid] = time.time() """
                #logging.info(f"Generated temporary UUID {temp_uuid} for client at {client_addr}")

                client_addr = context.peer()
                self.pending_nodes[temp_uuid] = client_addr

                logging.info(f"New node pending approval - UUID: {temp_uuid}, Address: {client_addr}")

                return storage_node_pb2.UUIDResponse(
                    success=False,
                    uuid=temp_uuid,
                    message="UUID generated successfully"
                )
            else:
                logging.warning("Invalid request type received in RequestUUID")
                return storage_node_pb2.UUIDResponse(
                    success=False,
                    message="Invalid request type"
                )
        except Exception as e:
            logging.error(f"Exception in RequestUUID: {e}", exc_info=True)
            context.abort(grpc.StatusCode.INTERNAL, "Internal error during UUID generation")
    
    def ValidateUUID(self, request, context):
        """Check if UUID was generated by this registry node and compare it to the incoming one"""
        """Validate provided UUID or add to pending if unknown."""
        try:
            client_uuid = request.uuid
            client_addr = context.peer()

            if client_uuid in self.nodes:
                # UUID known, approve connection immediately
                self.connected_clients[client_uuid] = client_addr
                self.client_last_heartbeat[client_uuid] = time.time()
                logging.info(f"Validated known UUID {client_uuid} for client at {client_addr}")
                return storage_node_pb2.UUIDResponse(
                    success=True,
                    uuid=client_uuid,
                    message="UUID validated successfully"
                )
            else:
                # Unknown UUID, add to pending list quietly after first warning
                if client_uuid not in self.pending_nodes:
                    self.client_last_heartbeat[client_uuid] = time.time() # if >15 seconds from last request, pending node removed
                    self.pending_nodes[client_uuid] = client_addr
                    # print(f"[DEBUG] received offer for {request.storage_capacity_mb}\n\n") # optional debug
                    logging.warning(f"New node pending approval - UUID: {client_uuid}, Address: {client_addr}")
                # Don't repeatedly log warnings

                # Prevent available snodes being periodically disconnected if
                # they send a request within (heartbeat check time) seconds
                else:
                    # print(f"[DEBUG] updating time for {client_uuid}\n") # optional debug
                    self.client_last_heartbeat[client_uuid] = time.time()

                self.pending_storage[client_uuid] = request.storage_capacity_mb
                self.pending_hostnames[client_uuid] = request.hostname

                return storage_node_pb2.UUIDResponse(
                    success=False,
                    uuid=client_uuid,
                    message="UUID pending approval from registry node."
                )

        except Exception as e:
            logging.error(f"Exception in ValidateUUID: {e}", exc_info=True)
            context.abort(grpc.StatusCode.INTERNAL, "Internal error during UUID validation")
   
    def get_total_storage(self) -> int:
        """Return the total storage capacity across all connected nodes in MB"""
        return sum(self.client_storage_capacity.values())

    def get_hostname(self, uuid: str) -> str:
        """Return hostname given UUID"""
        return self.client_hostnames.get(uuid, None)

    """ Return snode tribute storage given UUID"""
    def get_storage(self, uuid: str) -> str:
        return self.client_storage_capacity.get(uuid, None)

class RegistryNode:
    def __init__(self, service_type="_rnode._tcp.local.", service_name="rnode"):
        self.zeroconf = Zeroconf()
        self.service_type = service_type
        self.service_name = service_name
        self.full_name = f"{service_name}.{service_type}"
        self.server = None
        self.storage_service = StorageService()
        self.mappings_dir = "file_mappings"
        self.uuid_to_chunks = os.path.join(self.mappings_dir, "uuid_to_chunks.json")
        self.file_total_sizes = os.path.join(self.mappings_dir, "file_total_sizes.json")
        self.file_to_uuids = os.path.join(self.mappings_dir, "file_to_uuids.json")
        self.cloud = False

        os.makedirs(self.mappings_dir, exist_ok=True)

    def enableCloud(self):
        available=False
        if google_util.check_key():
            available = True
        if aws_util.check_key():
            available = True
        if available == True:
            self.cloud = True
    
    def disableCloud(self):
        self.cloud = False
        
    def download_from_cloud(self,file_path):
        basename = os.path.basename(file_path)
        google_list = google_util.get_full_name(basename)
        for file in google_list:
            google_util.download_from_gcs(file)
        aws_list = aws_util.get_full_name(basename)
        for file in aws_list:
            aws_util.download(file)
    
    def register_service(self, port: int):
        hostname = socket.gethostname()

        local_ip = network_utils.get_real_ip()
        info = ServiceInfo(
            type_=self.service_type,
            name=self.full_name,
            addresses=[socket.inet_aton(local_ip)],
            port=port,
            server=f"{hostname}.local."
        )
        self.zeroconf.register_service(info)
        logging.info(f"Registered service {self.full_name} on {local_ip}:{port}")

        # Create the gRPC server
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        storage_node_pb2_grpc.add_StorageServiceServicer_to_server(
            self.storage_service, self.server
        )
        # No SSL/TLS, won't matter since it's LAN(?)
        self.server.add_insecure_port(f'[::]:{port}')
        self.server.start()
        
        return info

    def unregister_service(self, info):
        if self.server:
            self.server.stop(0)
        self.zeroconf.unregister_service(info)
        self.zeroconf.close()

    def get_pending_hostname(self, uuid):
        # print(f"[DEBUG] now searching for uuid: {uuid}\n") # optional debug
        # print(f"[DEBUG] found {self.storage_service.pending_hostnames})
        return self.storage_service.pending_hostnames.get(uuid, None)
    
    def get_pending_storage(self, uuid):
        # print(f"[DEBUG] now searching for uuid: {uuid}\n") # optional debug
        # print(f"[DEBUG] found {self.storage_service.pending_storage}")
        return self.storage_service.pending_storage.get(uuid, "Unknown storage")

    def upload_file_to_snode(self, 
    target_uuid: str, filename: str):
        try:
            with open(self.uuid_to_chunks, 'r') as f:
                uuid_to_chunks = json.load(f)
            with open(self.file_total_sizes, 'r') as f:
                file_total_sizes = json.load(f)
            with open(self.file_to_uuids, 'r') as f:
                file_to_uuids = json.load(f)
                
        except (FileNotFoundError, json.JSONDecodeError):
            uuid_to_chunks = {}
            file_total_sizes = {}
            file_to_uuids = {}

        try:
            # Get the client context for the target storage node
            context = self.storage_service.client_contexts.get(target_uuid)
            if not context or target_uuid not in self.storage_service.connected_clients:
                print(f"Storage node {target_uuid} is not connected")
                return False
            
            client_addr = self.storage_service.connected_clients[target_uuid]
            ip = client_addr.split(':')[1]  # Get the IP address part
            port = self.storage_service.client_file_ports.get(target_uuid)
        
            # Create a channel to the storage node
            channel = grpc.insecure_channel(f'{ip}:{port}')

            # A stub is essentially an object that allows you to use the server methods like local functions
            stub = storage_node_pb2_grpc.StorageServiceStub(channel)
            chunk_size = os.path.getsize(filename)

            def file_chunk_generator():
                CHUNK_SIZE = 1024 * 1024  # 1MB chunks
                try:
                    with open(filename, 'rb') as f:
                        offset = 0
                        while True:
                            chunk = f.read(CHUNK_SIZE)
                            if not chunk:
                                break
                            yield storage_node_pb2.FileChunk(
                                content=chunk,
                                filename=os.path.basename(filename),
                                offset=offset,
                                total_size=chunk_size
                            )
                            offset += len(chunk)
                except FileNotFoundError:
                    print(f"File {filename} not found")
                    return
                except Exception as e:
                    print(f"Error reading file: {e}")
                    return

            # Send the file chunks to the storage node
            response = stub.UploadFile(file_chunk_generator())

            if response.success:
                # print(f"[DEBUG] File uploaded successfully: {response.message}")

                # update uuid file mappings here
                # chunk_name = (erasure) chunk name
                chunk_name = os.path.basename(filename)
                if target_uuid not in uuid_to_chunks:
                    uuid_to_chunks[target_uuid] = [chunk_name]
                if chunk_name not in uuid_to_chunks[target_uuid]:
                    uuid_to_chunks[target_uuid].append(chunk_name)
                
                # write new storage space taken by the file 
                full_file_name = chunk_name[:-2] 
                if target_uuid not in file_total_sizes:
                    file_total_sizes[full_file_name] = chunk_size
                else:
                    file_total_sizes[full_file_name] = file_total_sizes[full_file_name] + chunk_size
                
                # update {file: [uuids]}
                if target_uuid not in file_to_uuids:
                    file_to_uuids[full_file_name] = [target_uuid]
                else:
                    file_to_uuids[full_file_name].append(target_uuid)
                

                # write above changes to disk
                with open(self.uuid_to_chunks, 'w') as f:
                    json.dump(uuid_to_chunks, f, indent=4)
                with open(self.file_total_sizes, 'w') as f:
                    json.dump(file_total_sizes, f, indent=4)
                with open(self.file_to_uuids, 'w') as f:
                    json.dump(file_to_uuids, f, indent=4)
                
                return True
            else:
                print(f"Upload failed: {response.message}")
                return False

        except Exception as e:
            print(f"Upload error: {e}")
            return False
        
    def download_from_snode(self, filename: str) -> bool:
        try:
            with open(self.uuid_to_chunks, 'r') as f:
                mappings = json.load(f)
        except json.JSONDecodeError:
            print("Error reading mapping files")
            return False
        
        target_uuid = None
        for uuid, files in mappings.items():
            if filename in files:
                target_uuid = uuid
                break
        if not target_uuid:
            print(f"File {filename} is not in any storage node")
            return False
        
        try:
            # Check if node is connected
            if target_uuid not in self.storage_service.connected_clients:
                print(f"Storage node {target_uuid} is not connected")
                return False
                    
            client_addr = self.storage_service.connected_clients[target_uuid]
            ip = client_addr.split(':')[1]
            port = self.storage_service.client_file_ports.get(target_uuid)
            
            if not port:
                print(f"No file service port found for storage node {target_uuid}")
                return False
                
            # Create channel to storage node
            print(f"Connecting to storage node at {ip}:{port}")
            channel = grpc.insecure_channel(f'{ip}:{port}')
            stub = storage_node_pb2_grpc.StorageServiceStub(channel)
            
            # Prepare download request
            request = storage_node_pb2.FileRequest(filename=filename)
            os.makedirs("dlfiles", exist_ok=True)
            save_path = os.path.join("dlfiles", filename)

            total_size = 0
            with open(save_path, 'wb') as f:
                try:
                    for chunk in stub.RequestFile(request):
                        f.write(chunk.content)
                        total_size += len(chunk.content)
                        if chunk.total_size > 0:
                            progress = (total_size / chunk.total_size) * 100
                            print(f"\rDownloading: {progress:.1f}%", end="", flush=True)
                except grpc.RpcError as rpc_error:
                    print(f"\nRPC error: {rpc_error.code()}: {rpc_error.details()}")
                    if os.path.exists(save_path):
                        os.remove(save_path)
                    return False
                        
            print(f"File downloaded successfully to {save_path}")
            return True
            
        except Exception as e:
            print(f"Download error details: {str(e)}")
            print(f"Error type: {type(e)}")
            if 'save_path' in locals() and os.path.exists(save_path):
                os.remove(save_path)
            return False
        
    def get_random_snodes(self, n: int) -> List[str]:
        """Choose N random snodes"""


        connected_snodes = list(self.storage_service.connected_clients.keys())
        print(connected_snodes)

        if not connected_snodes:
            print("No storage nodes connected")
            return []
        
        # This should never really happen since our algorithm will control this and will always choose proper N
        # Perhaps maybe if snodes disconnect and something hasn't updated...
        if n > len(connected_snodes):
            print("Too many snodes requested")
            return []
        
        selected_snodes = random.sample(connected_snodes, n)
        return selected_snodes
    
    def upload_folder_to_snodes(self, folder_path: str) -> Dict[str, Tuple[str, bool]]:
        """Upload folder to n snodes, folder will have erasure coded files"""

        # Again, none of this error checking is really necessary because of how our program is set up linearly, probably
        if not os.path.isdir(folder_path):
            print(f"Folder {folder_path} does not exist")
            return {}
            
        # Get all files in folder
        files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
        
        if not files:
            print(f"No files found in {folder_path}")
            return {}
            
        n = len(files)
        print(n)
        snodes = self.get_random_snodes(n)
        print(snodes)
        
        if self.cloud==True:
            snodes.append("google")
            snodes.append("aws")
        if not snodes:
            print("No storage nodes available for upload")
            return {}
        

        num_files_to_upload = min(len(files), len(snodes))
        
        # Upload each file to a different storage node
        results = {}
        for i in range(num_files_to_upload):
            file_path = os.path.join(folder_path, files[i])
            snode_uuid = snodes[i]
            if snode_uuid == "google":
                try:
                    google_util.upload_to_gcs(file_path)
                    success = True
                except Exception as e: 
                    success = e

            elif snode_uuid == "aws":
                try:
                    aws_util.upload(file_path)
                    success = True
                except Exception as e:
                    success = e
            else:
                success = self.upload_file_to_snode(snode_uuid, file_path)
            
        return results
        
    def get_client_list(self) -> List[Dict[str, str]]:
        return [
            {
                'uuid': uuid, 
                'address': addr, 
                'hostname': self.storage_service.get_hostname(uuid),
                'storage': self.storage_service.client_storage_capacity.get(uuid, 0)
            }
            for uuid, addr in self.storage_service.connected_clients.items()
        ]

    def get_total_storage(self) -> int:
        """Return the total storage capacity across all connected nodes"""
        return self.storage_service.get_total_storage()   
    
    def get_pending_nodes(self) -> list:
        """Get list of nodes waiting for approval, that
        have already provided their storage and hostname, which
        occurs on the 2nd request from the snode to the rnode"""
        pending_nodes = []
        
        for uuid, address in self.storage_service.pending_nodes.items():
            if self.get_pending_hostname(uuid) and self.get_pending_storage(uuid):
                pending_nodes.append({
                    'uuid': uuid,
                    'address': address
                })
        
        return pending_nodes 

if __name__ == "__main__":
    service = RegistryNode()
    service_info = service.register_service(port=12345)

    try:
        while True:
            command = input("\nEnter command (list/pending/approve/reject/help/quit/upload/download/uploadfolder): ").strip().lower()
            
            if command == "help":
                print("\nAvailable commands:")
                print("  list        - List all connected clients")
                print("  pending      - List nodes pending approval")
                print("  approve      - Approve a pending node")
                print("  reject       - Reject a pending node")
                print("  upload      - Upload a file to a storage node")
                print("  download    - Download a file from a storage node")
                print("  uploadfolder - Upload all files from a folder across storage nodes")
                print("  help        - Show this help message")
                print("  quit        - Exit the program")
                
            elif command == "list":
                client_list = service.get_client_list()
                if not client_list:
                    print("No clients connected")
                else:
                    print("\nConnected Clients:")
                    for i, client in enumerate(client_list):
                        print(f"{i}: Hostname: {client['hostname']:<15} Address: {client['address']:<15} UUID: {client['uuid']} Storage: {client['storage']} GB")
            
            elif command == "upload":
                client_list = service.get_client_list()
                if not client_list:
                    print("No storage nodes connected")
                    continue
                    
                # Display available storage nodes
                print("\nAvailable storage nodes:")
                for i, client in enumerate(client_list):
                    print(f"{i}: Address: {client['address']:<15} UUID: {client['uuid']}")
                
                # Get target node
                try:
                    node_idx = int(input("\nEnter storage node number: "))
                    if node_idx < 0 or node_idx >= len(client_list):
                        print("Invalid storage node number")
                        continue
                except ValueError:
                    print("Invalid input")
                    continue
                
                # Get filename
                filename = input("Enter filename to upload: ").strip()
                if not filename:
                    print("Invalid filename")
                    continue
                
                # Attempt upload
                target_uuid = client_list[node_idx]['uuid']
                service.upload_file_to_snode(target_uuid, filename)

            elif command == "download":
                # Get filename to download
                filename = input("Enter filename to download: ").strip()
                if not filename:
                    print("Invalid filename")
                    continue
                
                # Attempt download
                if service.download_from_snode(filename):
                    print(f"Successfully downloaded {filename}")
                else:
                    print(f"Failed to download {filename}")
            
            elif command == "uploadfolder":
                # Check if there are enough storage nodes connected
                client_list = service.get_client_list()
                if not client_list:
                    print("No storage nodes connected")
                    continue
                
                # Get folder path
                folder_path = input("Enter folder path to upload: ").strip()
                if not folder_path:
                    print("Invalid folder path")
                    continue
                
                if not os.path.isdir(folder_path):
                    print(f"Folder {folder_path} does not exist")
                    continue
                
                # Count files in the folder
                files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
                
                if not files:
                    print(f"No files found in {folder_path}")
                    continue
                
                if len(files) > len(client_list):
                    print(f"Warning: Not enough storage nodes ({len(client_list)}) for all files ({len(files)})")
                    proceed = input("Continue with partial upload? (y/n): ").strip().lower()
                    if proceed != 'y':
                        continue
                
                # Upload folder to storage nodes
                results = service.upload_folder_to_snodes(folder_path)
                
                # Display results
                if results:
                    print("\nUpload results:")
                    for filename, (snode_uuid, success) in results.items():
                        status = "SUCCESS" if success else "FAILED"
                        print(f"{filename}: {status} -> Node: {snode_uuid}")
                    
                    success_count = sum(1 for _, success in results.values() if success)
                    print(f"\nSuccessfully uploaded {success_count}/{len(results)} files")
                else:
                    print("No files were uploaded")

            elif command == "pending":
                pending = service.storage_service.pending_nodes
                if not pending:
                    print("\nNo pending nodes.")
                else:
                    print("\nPending Nodes:")
                    for uuid, addr in pending.items():
                        print(f"UUID: {uuid}, Address: {addr}")

            elif command == "approve":
                uuid_to_approve = input("Enter UUID to approve: ").strip()
                pending = service.storage_service.pending_nodes
                if uuid_to_approve in pending:
                    # Approve and save node
                    service.storage_service.save_node(uuid_to_approve, "SNODE")
                    print(f"UUID {uuid_to_approve} approved successfully.")
                else:
                    print("UUID not found in pending nodes.")

            elif command == "reject":
                uuid_to_reject = input("Enter UUID to reject: ").strip()
                pending = service.storage_service.pending_nodes
                if uuid_to_reject in pending:
                    del pending[uuid_to_reject]
                    print(f"UUID {uuid_to_reject} rejected and removed from pending nodes.")
                else:
                    print("UUID not found in pending nodes.")
                    
            elif command == "storage":
                total_storage = service.get_total_storage()
                print(f"\nTotal available storage across all nodes: {total_storage} GB")

            elif command == "quit":
                break

            elif command == "pending":
                print(service.get_pending_nodes)
            else:
                print("Unknown command. Type 'help' for available commands.")
            
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        print("Unregistering service...")
        service.unregister_service(service_info)