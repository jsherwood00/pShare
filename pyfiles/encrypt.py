import base64
import hashlib
import os
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import sys
import binascii
from Crypto.Protocol.KDF import scrypt
import platform
import concurrent.futures
import math
import argparse
import cmd_util
import time
import binascii

import erasure
from checksum import store_checksum_and_salt
from password_manager import password_manager  # Import password manager

BUFFER_SIZE = 65535
KEY_LEN = 32
n_chunk_num = 3
p_chunk_num = 2

def setN(i: int):
    if i < 1: return "n chunk number need to > 1"
    global n_chunk_num
    n_chunk_num = i
    return None

def setP(i: int):
    if i < 0: return "p chunk number need to > 0"
    global p_chunk_num
    p_chunk_num = i
    return None

def resolve_path(file_path):
    """Resolve absolute paths for files outside the project folder."""
    if not os.path.isabs(file_path):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # Move up one level
        file_path = os.path.join(project_root, file_path)
    return file_path

# Ensure password is set before encryption/decryption
def ensure_password():
    """Check if a password is set; prompt user to create one if missing."""
    if password_manager.master_password is None:
        print("No stored password found. Please set a new one.")
        new_password = input("Enter new master password: ")
        password_manager.set_password(new_password)  # Save the new password

    # Ask for password verification before proceeding
    password = input("Enter your master password: ")
    if not password_manager.verify_password(password):
        print("Incorrect password! Process aborted.")
        exit(1)  # Stop execution if password verification fails
    print("Password verified.")

# Encrypt a single chunk
def encrypt_chunk(key, input_file_path, chunk_num, chunk_size):
    """Encrypts a chunk of a file using AES-GCM."""
    file_name = os.path.basename(input_file_path)
    with open(input_file_path, 'rb') as input_file:
        input_file.seek(chunk_num * chunk_size)
        plaintext = input_file.read(chunk_size)

    # Generate random salt
    salt = get_random_bytes(32)

    # AES key derivation using the salt
    key = scrypt(key, salt, key_len=KEY_LEN, N=2**20, r=8, p=1)

    # Encrypt using AES-GCM
    cipher = AES.new(key, AES.MODE_GCM)
    encrypted_data = cipher.encrypt(plaintext)
    tag = cipher.digest()

    # Store the salt + nonce + encrypted data
    with open(f"temp/{file_name}_info_/{file_name}_enc_{chunk_num}", "wb") as output:
        output.write(salt)
        output.write(cipher.nonce)
        output.write(encrypted_data)
        output.write(tag)

# Encrypt an entire file
def encrypt(input_file_path: str):
    """Encrypts a file by splitting it into chunks and using the master password."""

    ensure_password()  # Ensure the user enters a valid password before proceeding

    # Generate a salt for this file (before deriving the key)
    salt = get_random_bytes(16)  # Generate a 16-byte random salt

    # Store the checksum and salt together in hashes.json BEFORE key derivation
    store_checksum_and_salt(input_file_path, salt)

    # Now derive the encryption key using the stored salt
    key, _ = password_manager.derive_key(input_file_path)

    # Ensure temp directory exists
    if not cmd_util.check_exist("temp"):
        cmd_util.create_dir("temp")

    store_checksum_and_salt(input_file_path, salt)  # This line was redundant, so we keep only one call

    # Remove previously encrypted chunks if they exist
    temp_dir = f"temp/{os.path.basename(input_file_path)}_info_"
    if cmd_util.check_exist(temp_dir):
        cmd_util.remove_all(temp_dir)
    cmd_util.create_dir(temp_dir)

    file_size = os.path.getsize(input_file_path)
    chunk_size = int(file_size / n_chunk_num) + 1

    # Encrypt chunks in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = [executor.submit(encrypt_chunk, key, input_file_path, i, chunk_size) for i in range(n_chunk_num)]
        concurrent.futures.wait(futures)

    # Apply erasure coding for redundancy
    erasure.padding(os.path.basename(input_file_path), n_chunk_num)
    erasure.encode(os.path.basename(input_file_path), n_chunk_num, p_chunk_num)

    print(f"Encryption completed: {input_file_path}")


# Decrypt a single chunk
def decrypt_chunk(key, input_file_path, chunk_num: int):
    """Decrypts a single chunk of a file."""
    file_name = os.path.basename(input_file_path)
    chunk_path = f"temp/{file_name}_info_/{file_name}_dec_{chunk_num}"
    print(f"Decrypting {chunk_path}")

    with open(chunk_path, "rb") as input_file:
        salt = input_file.read(32)  # Read the stored salt
        nonce = input_file.read(16)  # Read the stored nonce
        
        # DEBUG: Print salt to ensure it's being read correctly
        print(f"Chunk {chunk_num} - Read Salt: {binascii.hexlify(salt)}")
        
        key = scrypt(key, salt, key_len=KEY_LEN, N=2**20, r=8, p=1)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)

        input_size = os.path.getsize(chunk_path)
        data_size = input_size - 64

        encrypted_data = input_file.read(data_size)
        tag = input_file.read(16)

        try:
            decrypted_data = cipher.decrypt(encrypted_data)
            cipher.verify(tag)  # Ensures data integrity
        except ValueError:
            print(f"MAC check failed for chunk {chunk_num} - possible key mismatch!")
            exit(1)

    return decrypted_data


# Decrypt an entire file
def decrypt(input_file_path: str):
    """Decrypts a file using the stored master password."""
    
    ensure_password()  # Ensure the user enters a valid password before proceeding

    # Generate the same key that was used for encryption
    key, _ = password_manager.derive_key(input_file_path)

    file_name = os.path.basename(input_file_path)
    err = erasure.decode(input_file_path=file_name, n_chunk_num=n_chunk_num, p_chunk_num=p_chunk_num)
    if err:
        return err

    err = erasure.depad(file_name, n_chunk_num)
    if err:
        return err

    # Decrypt each chunk in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        decryption_tasks = [executor.submit(decrypt_chunk, key, input_file_path, i) for i in range(n_chunk_num)]

        with open(input_file_path, "wb") as output:
            for task in decryption_tasks:
                decrypted_data = task.result()
                output.write(decrypted_data)

    # Clean up temporary decryption files
    cmd_util.remove_all(f"temp/{file_name}_info_")
    print(f"Decryption completed: {input_file_path}")

def main(args):
    """Handles user input for encryption and decryption."""
    
    file_path = resolve_path(args.filepath)

    if args.encrypt:
        if not os.path.exists(file_path):
            print("File to encrypt not found.")
            return -2

        if cmd_util.check_exist(f"temp/{os.path.basename(file_path)}_info_"):
            check = input("Encryption exists. Re-encrypt? (y/n): ")
            if check.lower() != 'y':
                return 0
            cmd_util.remove_all(f"temp/{os.path.basename(file_path)}_info_")

        start_time = time.time()
        encrypt(file_path)
        end_time = time.time()
        print("Encryption time:", end_time - start_time)
    else:
        if not cmd_util.check_exist(f"temp/{os.path.basename(file_path)}_info_"):
            print("No encrypted file found.")
            return -1

        start_time = time.time()
        decrypt(file_path)
        end_time = time.time()
        print("Decryption time:", end_time - start_time)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--filepath', type=str, required=True, help="File path for encryption/decryption")
    parser.add_argument('-n', '--num_chunks', type=int, default=3, help="Number of chunks (default: 3)")
    parser.add_argument('-e', '--encrypt', action='store_true', help="Enable encryption mode")
    parser.add_argument('-p', '--num_parity', type=int, default=2, help="Number of parity chunks (default: 2)")
    args = parser.parse_args()
    main(args)
