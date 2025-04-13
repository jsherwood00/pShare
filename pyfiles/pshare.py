import os

from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input, Label, Button
from textual.command import Hit, Hits, Provider
from textual.containers import Vertical, Container, VerticalScroll, Horizontal
import asyncio
import time

import cmd_util
import uuid_utils
import encrypt
import rnode as r_node
import snode as s_node
import erasurezfec as zfec
import json
import math
import shutil
import new_enc as enclib
import threading

""" pShare API """
class pShare(App):

    def __init__(self):
        """ By running the frontend, causes the device to broadcast both as an snode and rnode, which
        in the future can be toggled in settings """
        self.rnode = r_node.RegistryNode()
        self.snode = s_node.StorageNode()
        self.service_info = self.rnode.register_service(port=12345)
        enclib.setup_registry_directories()


    def pFiles(self):
        """Return {uuid: kb}, {filename: availability (bool)}, {filename: encrypted filename}, 
            to be displayed on index.html 
        """
        try:
            with open(self.rnode.file_total_sizes, 'r') as f:
                file_total_sizes = json.load(f) # {filename: size}
                file_sizes_kb = {}
                files_to_encfiles = {}
                for item in file_total_sizes.items():
                    # decrypt_filename produces: {'original_filename': 'name', 'key': 'key'}
                    decrypted_filename = enclib.decrypt_filename(item[0])['original_filename']
                    file_sizes_kb[decrypted_filename] = math.ceil(item[1] / 1000)
                    files_to_encfiles[decrypted_filename] = item[0]

            file_availability = self.rnode.index_availability() # {filename: availability}
            
            # create a non-blocking thread in rnode.py to clear all zombies from connected S-nodes
            threading.Thread(target=self.rnode.clear_zombies, daemon=True).start()
            
        except (json.JSONDecodeError, FileNotFoundError):
            print("[ERROR] reading mapping files or no files stored yet")
            return None, None, None
             
        return file_sizes_kb, file_availability, files_to_encfiles


    def pDistribute(self, filename, required_storage):
        """Distribute the file the user has selected, see erasurezfec.py for description 
            m = blocks produced, k = num blocks required to reconstruct, parity = m - k

            Uploading the same file twice potentially causes a problem due to our algorithm,
            as 2 nodes may end up with the same chunk when the requirement is that each snode
            store a different chunk for any given file 
        """
        try:
            with open(self.rnode.file_to_uuids, 'r') as f:
                file_to_uuids = json.load(f) # {filename: [uuids]}
            if filename in file_to_uuids:
                raise Exception("Cannot upload the same file twice (first delete the original)")

            ready_clients = self.rnode.fill_storage_request(required_storage) # ready to complete the request
            m = len(ready_clients) # total chunks = num_snodes
            if m == 0:
                return -1
            
            k = encrypt.genChunkNum(self.rnode, m) # k = num_parity
            self.rnode.distribute(filename, ready_clients, m, k)

        except Exception as e:
            print(f"[ERROR] on distribute: {e}")
            


    def pFileToSnodeAvailability(self, file_name):
        """Return {snode_name: connected_status} with all snodes storing the specified file"""
        return self.rnode.availability_util(file_name)


    def pRetrieve(self, user_files):
        """Download all files specified by the user_files list of file names"""
        for filename in user_files:
            encrypted_filename = enclib.encrypt_filename(filename)
            if not self.rnode.download(encrypted_filename):
                raise Exception(f"Failed to downloaded {encrypted_filename}")


    def pDelete(self, user_files):
        """Delete all files specified in user_files ([])"""
        for file in user_files:
            encrypted_filename = enclib.encrypt_filename(file)
            self.rnode.delete_file(encrypted_filename)


    def pSnodes(self):
        """Return {uuid: (hostname, storage)} for all connected S-nodes"""
        connected_snodes = self.rnode.get_client_list()
        connected_names_storage = {}
        used_storage_total = 0 # used storage summed over connected S-nodes

        for connected_snode in connected_snodes:
            uuid = connected_snode["uuid"]
            used_storage = self.rnode.get_used_storage(uuid)
            used_storage_mb = round(used_storage / 1000000, 1) # bytes to megabytes
            used_storage_total = used_storage_total + used_storage
            connected_names_storage[uuid] = (connected_snode["hostname"], used_storage_mb, connected_snode["storage"])

        used_storage_total = round(used_storage_total / 1000000, 1) # pass as MB

        return connected_names_storage, used_storage_total


    def pNumSnodes(self):
        """Return number of connected S-nodes"""
        connected_clients = self.rnode.storage_service.connected_clients.items()
        return len(connected_clients)


    def pRnodes(self):
        """TODO: Return a dictionary of RNODES the local SNODE is connected to, or None"""
        placeholder = {'RNODE computer name': 503, 'RNODE laptop 3': 115, 'RNODE server': 500}
        return placeholder


    def pAvailableRnodes(self):
        """TODO: Return a dictionary of RNODES broadcasting on the local network"""
        placeholder = {'Available RNODE computer name': 3, 'Available RNODE laptop 3': 5, 'Available RNODE server': 5}
        return placeholder


    def pAddRnode(self, rnode_name, storage_mb):
        """TODO: Given the name of an RNODE, sends a connection request with the SNODE
        Note: must provide a unique name for each SNODE
        idea: maybe if 2 devices with the same name connect, 1 has (1) added? 
        Also receives the storage amount the SNODE is willing to give to the RNODE, in mb
        """
        pass


    def pRemoveRnode(self, rnode_names):
        """TODO: disconnect from the specified R-node(s) ([])"""
        pass


    def pAvailableSnodes(self):
        """Return pending snodes: {uuid: (hostname, storage)}"""
        pending_snodes = self.rnode.get_pending_nodes()
        pending_names_storage = {}
        for pending_snode in pending_snodes:
            pending_names_storage[pending_snode["uuid"]] = (self.rnode.get_pending_hostname(pending_snode["uuid"]),  self.rnode.get_pending_storage(pending_snode["uuid"]))
        return pending_names_storage


    def pRemoveSnode(self, snode_name):
        """Remove the connection between the current RNODE and the specified SNODEs"""
        self.rnode.remove_client(snode_name)
        pass


    def pAddSnode(self, selected_uuids):
        """Add the connection between the current RNODE and the specified SNODE,
        selected_uuids is a list with strings of snode(s) uuid(s) """
        for selected_uuid in selected_uuids:
            all_pending_uuids = self.rnode.storage_service.pending_nodes
            if selected_uuid in all_pending_uuids:
                self.rnode.storage_service.save_node(selected_uuid, "SNODE")


    def pTotalStorage(self):
        """Return the amount of storage available across all SNODES the RNODE
        is connected to"""
        return self.rnode.get_total_storage()