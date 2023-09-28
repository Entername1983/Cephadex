import boto3
import logging
from botocore.exceptions import ClientError
import os
logger = logging.getLogger("flask_app")
AWS_ACCESS_KEY= os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION")
session = boto3.Session(
aws_access_key_id=AWS_ACCESS_KEY,
aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
region_name=AWS_DEFAULT_REGION
)

s3_client = session.client('s3')
boto3.set_stream_logger('boto3.resources', logging.DEBUG)


def upload_to_s3(bucket, folder, file_name, object_name=None):
    if object_name is None:
        object_name = file_name
    if folder:
        object_name = f"{folder}/{object_name}"
    
    try:
        s3_client.upload_file(file_name, bucket, object_name)
    except ClientError as e:
        logger.error(e)
        return False

    logger.info(f"Uploaded {file_name} to {bucket}/{object_name}")
    return True


def get_s3_object_in_folder(bucket_name, folder_name, object_name):
    object_key = f"{folder_name}/{object_name}"
    try:
        object = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        return object
    except ClientError as e:
        logger.error(f"Could not find {object_key} in {bucket_name} error: {e}")
        return False


def delete_s3_object_in_folder(bucket_name, folder_name, object_name):
    object_key = f"{folder_name}/{object_name}"
    try:
        response = s3_client.delete_object(Bucket=bucket_name, Key=object_key)
        logger.info(f"Deleted {object_key} from {bucket_name}, response {response}")
        if response["ResponseMetadata"]["HTTPStatusCode"] == 204:  
            logger.info(f"Deleted {object_key} from {bucket_name}")
            return True
        else:
            logger.info(f"Failed to delete {object_key} from {bucket_name}. Response: {response}")
            return False
    except ClientError as e:
        logger.info(f"Could not delete {object_key} from {bucket_name} error: {e}")
        return False