from google.cloud import storage

storage_client = storage.Client()


def read_binary_object(bucket_name: str, blob_name: str):
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.get_blob(blob_name, storage_client)

    return blob.download_as_bytes()


def read_file(file_path: str, mode: str = "rb"):
    with open(file_path, mode=mode) as file:
        data = file.read()
    return data


def file_exists(bucket_name: str, file_name: str):
    bucket = storage_client.bucket(bucket_name)
    stats = storage.Blob(bucket=bucket, name=file_name).exists(storage_client)
    return stats


def write_gcs_blob(bucket_name: str, file_name: str, content_as_str: str, content_type: str = "text/plain"):
    bucket = storage_client.get_bucket(bucket_name)
    gcs_file = bucket.blob(file_name)
    gcs_file.upload_from_string(content_as_str, content_type=content_type)
