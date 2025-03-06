from google.cloud import storage
import os
from google.oauth2 import service_account


KEY_PATH = "./capstone.json"
credentials = service_account.Credentials.from_service_account_file(KEY_PATH)

def check_key():
    return cmd_util.check_exist(KEY_PATH)
    
# Initialize the client for Google Cloud Storage
def get_storage_client():
    return storage.Client(credentials=credentials, project=credentials.project_id)

# Upload a file to Google Cloud Storage
def upload_to_gcs(bucket_name, source_file_name, destination_blob_name):
    # Get the storage client
    client = get_storage_client()
    
    # Get the bucket
    bucket = client.get_bucket(bucket_name)
    
    # Create a blob (object) in the bucket
    blob = bucket.blob(destination_blob_name)
    
    # Upload the file to GCS
    blob.upload_from_filename(source_file_name)
    print(f"File {source_file_name} uploaded to {destination_blob_name}.")

# Download a file from Google Cloud Storage
def download_from_gcs(bucket_name, source_blob_name, destination_file_name):
    # Get the storage client
    client = get_storage_client()
    
    # Get the bucket
    bucket = client.get_bucket(bucket_name)
    
    # Get the blob (object)
    blob = bucket.blob(source_blob_name)
    
    # Download the file
    blob.download_to_filename(destination_file_name)
    print(f"File {source_blob_name} downloaded to {destination_file_name}.")


def create_bucket(bucket_name, location="US"):
    # Get the storage client
    client = get_storage_client()
    
    # Create a new bucket
    bucket = client.bucket(bucket_name)
    
    # Set the location of the bucket (optional; default is 'US')
    bucket.location = location
    
    # Create the bucket in Google Cloud Storage
    bucket = client.create_bucket(bucket)
    print(f"Bucket {bucket.name} created in {bucket.location}.")


def list_buckets(project_id=credentials.project_id):
    # Set up credentials and create the storage client
    client = storage.Client(credentials=credentials, project=project_id)
    
    # List all buckets in the project
    buckets = client.list_buckets()
    
    # Print the bucket names
    print(f"Buckets in project {project_id}:")
    for bucket in buckets:
        print(bucket.name)

def delete_file(bucket_name:str,file_name:str):
    client = get_storage_client()
    bucket = client.bucket(bucket_name)
    file = bucket.blob(file_name)
    file.delete()


if __name__ == "__main__":
    # Replace with your bucket name
    bucket_name = 'availabletestbucket'
    # create_bucket(bucket_name)
    list_buckets()
    
    # Upload example
    source_file_name = './hashes.json'  # The local file to upload
    destination_blob_name = 'hashes.json'  # The name of the object in GCS
    upload_to_gcs(bucket_name, source_file_name, destination_blob_name)

    # Download example
    source_blob_name = 'hashes.json'  # The object name in GCS
    destination_file_name = 'hashes.json'  # Local path to save the file
    download_from_gcs(bucket_name, source_blob_name, destination_file_name)
    delete_file(bucket_name,destination_blob_name)
