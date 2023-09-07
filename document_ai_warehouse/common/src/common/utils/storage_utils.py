import re

from google.cloud import storage

storage_client = storage.Client()


def read_binary_object(bucket_name, blob_name):
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.get_blob(blob_name, storage_client)

    return blob.download_as_bytes()


def read_file(file_path: str, mode="rb"):
    with open(file_path, mode=mode) as file:
        data = file.read()
    return data


def file_exists(bucket_name: str, file_name: str):
    bucket = storage_client.bucket(bucket_name)
    stats = storage.Blob(bucket=bucket, name=file_name).exists(storage_client)
    return stats


def write_gcs_blob(bucket_name, file_name, content_as_str, content_type="text/plain"):
    bucket = storage_client.get_bucket(bucket_name)
    gcs_file = bucket.blob(file_name)
    gcs_file.upload_from_string(content_as_str, content_type=content_type)


def split_uri_2_bucket_prefix(uri: str):
    match = re.match(r"gs://([^/]+)/(.+)", uri)
    if not match:
        # just bucket no prefix
        match = re.match(r"gs://([^/]+)", uri)
        return match.group(1), ""
    bucket = match.group(1)
    prefix = match.group(2)
    return bucket, prefix
