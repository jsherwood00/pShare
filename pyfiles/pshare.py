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


""" pShare API """
class pShare(App):

    """ By running the frontend, causes the device to broadcast both as an snode and rnode, which
    in the future can be toggled in settings """
    def __init__(self):
        self.rnode = r_node.RegistryNode()
        self.snode = s_node.StorageNode()
        self.service_info = self.rnode.register_service(port=12345)


    def pFiles(self):
        try:
            """ For displaying which chunks each snode stores """
            with open(self.rnode.uuid_to_chunks, 'r') as f:
                uuid_to_chunks = json.load(f) # {uuid: [names]}
                # print(f"[DEBUG] UUIDs to chunk names: {uuid_to_chunks} \n")

            """ For displaying files: sizes (index page)"""
            with open(self.rnode.file_total_sizes, 'r') as f:
                file_total_sizes = json.load(f) # {filename: size}
                file_sizes_kb = {}
                for item in file_total_sizes.items():
                    file_sizes_kb[item[0]] = math.ceil(item[1] / 1000)
                # print(f"[DEBUG] Names to sizes: {file_total_sizes} \n")

            """ When click on an "available" cell, displays more info """
            with open(self.rnode.file_to_uuids, 'r') as f:
                file_to_uuids = json.load(f) # {filename: [uuids]}
                # print(f"[DEBUG] Names to UUIDs: {file_to_uuids} \n")

        except (json.JSONDecodeError, FileNotFoundError):
            print("Error reading mapping files or no files stored yet")
            return {}
             
        return file_sizes_kb


    """ Distribute the file the user has selected, see erasurezfec.py for description 
        m = blocks produced, k = num blocks required to reconstruct, parity = m - k
        TODO: add encryption """
    def pDistribute(self, absolute_path, filename):
        client_list = self.rnode.get_client_list()
        uuids = [client["uuid"] for client in client_list]
        m = len(client_list) # total chunks = num_snodes
        k = encrypt.genChunkNum(self.rnode) # k = num_parity
        output_dir = os.path.join(os.getcwd(), "file_chunked")

        try:
            # takes file from pyfiles/uploading_files, creates (m, k) chunks in pyfiles/file_chunked
            if (zfec.encode_file(input_file = absolute_path, output_dir = output_dir, m = m, k = k)):
            # On success, uploads (cwd)/file_chunked/filename.{i} to snode[i], 
            #..., (cwd)/file_chunked/file_name.{m} to snode[n]
                for i in range(m):
                    chunk_name = f"{filename}.{i}"
                    chunk_dir = os.path.join(os.getcwd(), "file_chunked")
                    chunk_path_i = os.path.join(chunk_dir, chunk_name)
                    self.rnode.upload_file_to_snode(uuids[i], chunk_path_i)
                    os.remove(chunk_path_i) # clear the folder
        except Exception as e:
            print(f"[ERROR] While attempting to upload file, encountered: {e}")



    """ TODO: download all specified files, if they exist """
    """ user_files is a list of file names """
    def pRetrieve(self, user_files):
        print(f"[DEBUG] downloading: {user_files}")
        for filename in user_files:
            if self.rnode.download_from_snode(filename):
                print(f"Successfully downloaded {filename}")
            else:
                print(f"Failed to download {filename}")


    """ TODO: deletes all specified files, if they exist """
    """ user_files is a list of file names """
    def pDelete(self, user_files):
        print(f"[DEBUG] deleting: {user_files}")
        pass

    """ Returns connected snodes: {uuid: (hostname, storage)} """
    def pSnodes(self):
        connected_snodes = self.rnode.get_client_list()
        connected_names_storage = {}
        for connected_snode in connected_snodes:
            connected_names_storage[connected_snode["uuid"]] = (connected_snode["hostname"], connected_snode["storage"])
        return connected_names_storage


    """ Number of connected snodes """
    def pNumSnodes(self):
        connected_clients = self.rnode.storage_service.connected_clients.items()
        return len(connected_clients)


    """ TODO: returns a dictionary of RNODES the local SNODE is connected to, or none """
    def pRnodes(self):
        placeholder = {'RNODE computer name': 503, 'RNODE laptop 3': 115, 'RNODE server': 500}
        return placeholder


    """ TODO: Returns a dictionary of RNODES broadcasting on the local network """
    def pAvailableRnodes(self):
        placeholder = {'Available RNODE computer name': 3, 'Available RNODE laptop 3': 5, 'Available RNODE server': 5}
        return placeholder


    """ TODO: Given the name of an RNODE, sends a connection request with the SNODE
        Note: must provide a unique name for each SNODE
        idea: maybe if 2 devices with the same name connect, 1 has (1) added? 
        Also receives the storage amount the SNODE is willing to give to the RNODE, in mb"""
    def pAddRnode(self, rnode_name, storage_mb):
        pass


    """ TODO """
    def pRemoveRnode(self, rnode_names):
        pass


    """ Returns pending snodes: {uuid: (hostname, storage)} """
    def pAvailableSnodes(self):
        pending_snodes = self.rnode.get_pending_nodes()
        pending_names_storage = {}
        for pending_snode in pending_snodes:
            pending_names_storage[pending_snode["uuid"]] = (self.rnode.get_pending_hostname(pending_snode["uuid"]),  self.rnode.get_pending_storage(pending_snode["uuid"]))
        return pending_names_storage


    """ Remove the connection between the current RNODE and the specified SNODE
        snode_name is a string with the name of the snode(s) """
    def pRemoveSnode(self, snode_names):
        pass


    """ Add the connection between the current RNODE and the specified SNODE
        selected_uuids is a list with strings of snode(s) uuid(s) """
    def pAddSnode(self, selected_uuids):
        for selected_uuid in selected_uuids:
            all_pending_uuids = self.rnode.storage_service.pending_nodes
            if selected_uuid in all_pending_uuids:
                print(f"\n[DEBUG] Saving {selected_uuid}")
                self.rnode.storage_service.save_node(selected_uuid, "SNODE")

    """ Returns the amount of storage available across all SNODES the RNODE
        is connected to """
    def pTotalStorage(self):
        return self.rnode.get_total_storage()


    """ TODO: Returns the amount of storage used across all SNODES the RNODE
        is connected to """
    def pUsedStorage(self):
        return 1