import socket
import time
import json
import struct
import select
from pathlib import Path
from typing import Dict, Tuple
import sys
import network_utils
import uuid_utils
from zeroconf import ServiceBrowser, Zeroconf, ServiceListener

import threading
import grpc
from concurrent import futures

import storage_node_pb2
import storage_node_pb2_grpc
import os

# This specifically finds .rnodes._tcp.local. (zeroconf)
class RNodeListener(ServiceListener):
    """..."""
    def __init__(self):
        # Store all the RNodes found (IP addr, Port)
        # In current implementations, we will just be testing for one RNode.
        self.registry_nodes: Dict[str, Tuple[str, int]] = {}
        self.found_service = False

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        if name in self.registry_nodes:
            print(f"Service {name} removed")
            del self.registry_nodes[name]

    # RNode discovery occurs here
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info:
            address = socket.inet_ntoa(info.addresses[0])
            print(f"Discovered Registry Node at {address}:{info.port}")
            self.registry_nodes[name] = (address, info.port)
            self.found_service = True

class StorageService(storage_node_pb2_grpc.StorageServiceServicer):
    def __init__(self):
        self.files_dir = "storage_node_files"
        os.makedirs(self.files_dir, exist_ok=True)
    
    # Handle a file upload from the registry node
    def UploadFile(self, request_iterator, context):
        filename = None
        file_path = None
        file_size = 0
        start_time = time.time()
        received_size = 0

        try:
            for chunk in request_iterator:
                if filename is None:
                    filename = chunk.filename
                    file_path = os.path.join(self.files_dir, filename)
                    file_size = chunk.total_size

                with open(file_path, 'ab') as f:
                    f.write(chunk.content)
                    received_size += len(chunk.content)
                    progress = (received_size / file_size) * 100
                    print(f"\rReceiving: {progress:.1f}% ({received_size:,}/{file_size:,} bytes)", 
                          end="", flush=True)

            end_time = time.time()
            duration = end_time - start_time
            speed_mbps = (file_size / (1024 * 1024)) / duration

            print(f"\nFile received and saved as {file_path}")
            print(f"Transfer speed: {speed_mbps:.2f} MB/s ({duration:.2f} seconds)")

            return storage_node_pb2.FileResponse(
                success=True,
                message=f"File uploaded successfully at {speed_mbps:.2f} MB/s",
                size=file_size
            )

        except Exception as e:
            print(f"\nError during file upload: {e}")
            return storage_node_pb2.FileResponse(
                success=False,
                message=f"Upload failed: {str(e)}"
            )
    
    def RequestFile(self, request, context):

        try:
            filename = request.filename
            file_path = os.path.join(self.files_dir, filename)
            
            if not os.path.exists(file_path):
                context.abort(grpc.StatusCode.NOT_FOUND, f"File {filename} not found")
                return
            
            file_size = os.path.getsize(file_path)
            CHUNK_SIZE = 1024 * 1024  # 1MB chunks
            
            with open(file_path, 'rb') as f:
                offset = 0
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                        
                    yield storage_node_pb2.FileChunk(
                        content=chunk,
                        filename=filename,
                        offset=offset,
                        total_size=file_size
                    )
                    offset += len(chunk)
                    
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, f"Error streaming file: {str(e)}")

class StorageNode:
    """"""
    def __init__(self):
        self.channel: grpc.Channel | None = None  # Channel represents a gRPC server essentially
        self.stub: storage_node_pb2_grpc.StorageServiceStub | None = None # Client side object that implements same methods as channel (essentially use the interface of the server to talk to it)
        self.uuid: str | None = None
        self.connected: bool = False

        # Directory setup
        self.files_dir = "storage_node_files"
        os.makedirs(self.files_dir, exist_ok=True)
        self.conf_dir = Path("storage_conf")
        self.uuid_file = self.conf_dir / "saved_uuid.json"
        self.conf_dir.mkdir(exist_ok=True)

        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
        self.service = StorageService()
        storage_node_pb2_grpc.add_StorageServiceServicer_to_server(
            self.service, self.server
        )
        
        # Use a random available port
        self.server_port = self.server.add_insecure_port('[::]:0')
        self.server.start()
        print(f"Started file service on port {self.server_port}")


    def _load_uuid(self) -> str | None:
        """Load UUID from config file"""

        # If JSON file exists, load UUID and return UUID, if not, return None.
        try:
            if self.uuid_file.exists():
                with self.uuid_file.open('r') as f:
                    data = json.load(f)
                    return data.get('uuid')
        except (json.JSONDecodeError, IOError):
            return None
    
    def _save_uuid(self, uuid: str) -> None:
        """Saved UUID to config file"""
        with self.uuid_file.open('w') as f:
            json.dump({'uuid': uuid}, f, indent = 2)

    # Method to send a heartbeat to registry node to say it's still up and running
    def _start_heartbeat(self):
        # Send a heartbeat every 5 seconds containing the UUID of this storage node and the timestamp
        def heartbeat_stream():
            while self.connected:
                try:
                    yield storage_node_pb2.HeartbeatRequest(
                        uuid=self.uuid,
                        timestamp=int(time.time()),
                        file_service_port=self.server_port
                    )
                    time.sleep(5)
                except Exception as e:
                    print(f"Heartbeat error: {e}")
                    self.connected = False
                    break

        # Process response from server
        def handle_heartbeat_responses():
            try:
                responses = self.stub.Heartbeat(heartbeat_stream())
                for response in responses:
                    if not response.success:
                        print(f"Heartbeat failed: {response.message}")
                        self.connected = False
                        break
            # In case of rnode disconnection
            except grpc.RpcError as e:
                print(f"Heartbeat stream error: {e}")
                self.connected = False
            except Exception as e:
                print(f"Unexpected heartbeat error: {e}")
                self.connected = False

        # Use a thread to do the heartbeat function
        threading.Thread(target=handle_heartbeat_responses, daemon=True).start()

    def connect_to_rnode(self, rnode_address: str, rnode_port: int) -> bool:
        try:
            # Insecure channel can be changed, not looking into it currently, but it is "insecure" -- doesn't matter on a LAN network probably
            self.channel = grpc.insecure_channel(f'{rnode_address}:{rnode_port}')
            self.stub = storage_node_pb2_grpc.StorageServiceStub(self.channel)

            # If a UUID does not exist, request one from the rnode, if one does exist, send the UUID for the rnode to validate.
            stored_uuid = self._load_uuid()
            if stored_uuid is None:
                request = storage_node_pb2.UUIDRequest(type='request_uuid')
                response = self.stub.RequestUUID(request)
                if response.success:
                    self._save_uuid(response.uuid)
                    self.uuid = response.uuid
                    print(f"Received UUID from RNode: {response.uuid}")
                else:
                    print(f"Failed to obtain UUID: {response.message}")
                    return False
            else:
                request = storage_node_pb2.UUIDValidation(uuid=stored_uuid)
                response = self.stub.ValidateUUID(request)
                if response.success:
                    self.uuid = stored_uuid
                    print(f"RNode acknowledged UUID: {stored_uuid}")
                else:
                    print(f"UUID validation failed: {response.message}")
                    return False
            # After UUID handshake finishes, mark self as connected and start sending heartbeats to the rnode
            self.connected = True
            self._start_heartbeat()

            return True
        
        except grpc.RpcError as e:
            print(f"RPC failed: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False
    
    def disconnect(self) -> None:
        if self.channel:
            self.channel.close()
            self.channel = None
            self.stub = None
            self.connected = False
            self.uuid = None

def discover_rnodes() -> Dict[str, Tuple[str, int]]:
    zeroconf = Zeroconf(interfaces=[network_utils.get_real_ip()])
    listener = RNodeListener()
    ServiceBrowser(zeroconf, "_rnode._tcp.local.", listener)
    # Wait for nodes to be found
    time.sleep(4)
    zeroconf.close()
    return listener.registry_nodes

if __name__ == "__main__":
    rnodes = discover_rnodes()
    if not rnodes:
        print("No registry nodes found")
        sys.exit()

    storage_node = StorageNode()

    # Connect to the first rnode
    first_node_name = next(iter(rnodes))
    address, port = rnodes[first_node_name]
    
    print(f"Attempting to connect to registry node at {address}:{port}")
    if storage_node.connect_to_rnode(address, port):
        try:
            print("Connected to registry node...")
            # Keep this program alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nDisconnecting...")
        finally:
            storage_node.disconnect()
    else:
        print("Failed to connect to registry node")