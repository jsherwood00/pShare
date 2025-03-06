import boto3
import json
import io
import os
import cmd_util
from boto3.s3.transfer import S3UploadFailedError
from botocore.exceptions import ClientError

def check_key():
    return cmd_util.check_exist("key.json")

def load_s3_source():
    with open('key.json', 'r') as f:
        data = json.load(f)
    s3_resource = boto3.resource("s3",aws_access_key_id=data['aws_access_id'],aws_secret_access_key=data['aws_access_key'])
    print("Hello, Amazon S3! Let's list your buckets:")

    
    return s3_resource

s3_resource = load_s3_source()

def get_bucket_name(s3_resource):
    buckets = []
    for bucket in s3_resource.buckets.all():
        buckets.append(bucket.name)
    return buckets

def check_bucket_exist(s3_resource,bucket_name:str):
    buckets = get_bucket_name(s3_resource)
    if bucket_name in buckets:
        return True
    return False

def upload(bucket_name,file_name:str):
    
    bucket = s3_resource.Bucket(bucket_name)
    file_obj = bucket.Object(os.path.basename(file_name))
    try:
        file_obj.upload_file(file_name)
        return 0
    except S3UploadFailedError as err:
        print(f"Couldn't upload file {file_name} to {bucket.name}.")
        print(f"\t{err}")
        return -1


def download(bucket_name,file_name:str):
    bucket = s3_resource.Bucket(bucket_name)
    dest_obj = bucket.Object(os.path.basename(file_name))
    data = io.BytesIO()
    try:
        dest_obj.download_file(dest_obj.key)
        # data.seek(0)
        cmd_util.move_file(dest_obj.key,file_name)
        print(f"Got your object. File: {file_name}\n")
        # print(f"\t{data.read()}")
    except ClientError as err:
        print(f"Couldn't download {dest_obj.key}.")
        print(
            f"\t{err.response['Error']['Code']}:{err.response['Error']['Message']}"
    )

def delete_file(bucket_name:str,file_name:str):
    bucket = s3_resource.Bucket(bucket_name)
    s3_resource.Object(bucket_name=bucket_name, key=file_name).delete()
