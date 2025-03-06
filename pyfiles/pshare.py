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
import rnode
import json


""" pshare API """
class pShare(App):

    def __init__(self):
        self.service = rnode.RegistryNode()
        self.service_info = self.service.register_service(port=12345)


    def pFiles(self):
        try:
            with open(self.service.mappings_file, 'r') as f:
                mappings = json.load(f)
        except json.JSONDecodeError:
            print("Error reading mapping files")
            return False
        
        file_names = []
        for uuid, stored_files in mappings.items():
            file_names.extend(stored_files)
            
        print(f"[DEBUG]: file list: {file_names}")
        files = {file_name: "unknown" for file_name in file_names}

        return files


    """ TODO: distribute the file the user has selected to all SNODES """
    """ user_file is a file object """
    def pDistribute(self, absolute_path):
        print(f"Received the path: {absolute_path}")
        client_list = self.service.get_client_list()
        if client_list:
            first_client_uuid = client_list[0]['uuid']
            self.service.upload_file_to_snode(first_client_uuid, absolute_path)



    """ TODO: download all specified files, if they exist """
    """ user_files is a list of file names """
    def pRetrieve(self, user_files):
        print(f"[DEBUG] downloading: {user_files}")
        for filename in user_files:
            if self.service.download_from_snode(filename):
                print(f"Successfully downloaded {filename}")
            else:
                print(f"Failed to download {filename}")


    """ TODO: deletes all specified files, if they exist """
    """ user_files is a list of file names """
    def pDelete(self, user_files):
        print(f"[DEBUG] deleting: {user_files}")
        pass


    """ TODO: returns a dictionary of SNODES the local RNODE is connected to, or none """
    def pSnodes(self):
        snodes = {'SNODE computer name': 50, 'SNODE laptop 3': 15, 'SNODE server': 5000}
        print(self.service.get_client_list())
        # this returns uuid: address, without name info. This on cannot be completed
        # until uuid -> name (or similar) functionality is added
        return snodes


    """ TODO: returns a dictionary of RNODES the local SNODE is connected to, or none """
    def pRnodes(self):
        placeholder = {'RNODE computer name': 503, 'RNODE laptop 3': 115, 'RNODE server': 500}
        return placeholder


    """ TODO: Returns a dictionary of RNODES broadcasting on the local network """
    def pAvailableRnodes(self):
        placeholder = {'Available RNODE computer name': 3, 'Available RNODE laptop 3': 5, 'Available RNODE server': 5}
        return placeholder


    """ Given the name of an RNODE, sends a connection request with the SNODE
        Note: must provide a unique name for each SNODE
        idea: maybe if 2 devices with the same name connect, 1 has (1) added? 
        Also receives the storage amount the SNODE is willing to give to the RNODE, in mb"""
    def pAddRnode(self, rnode_name, storage_mb):
        pass

    def pRemoveRnode(self, rnode_names):
        pass


    """ TODO: Returns a dictionary of SNODES that have requested to
        connect to the current RNODE on the local network"""
    def pAvailableSnodes(self):
        placeholder = {'Available SNODE 1': 20, 'Available SNODE 2': 230, 'Available SNODE 3': 2}
        return placeholder


    """ Remove the connection between the current RNODE and the specified SNODE
        snode_name is a string with the name of the snode(s) """
    def pRemoveSnode(self, snode_names):
        pass


    """ Add the connection between the current RNODE and the specified SNODE
        snode_name is a string with the name of the snode(s) """
    def pAddSnode(self, snode_names):
        pass


    """ TODO: Returns the amount of storage available across all SNODES the RNODE
        is connected to """
    def pAvailableStorage(self):
        return 2


    """ TODO: Returns the amount of storage used across all SNODES the RNODE
        is connected to """
    def pUsedStorage(self):
        return 1