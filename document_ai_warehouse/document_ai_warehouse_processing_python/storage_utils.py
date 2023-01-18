from google.cloud import storage


def read_binary_object(bucket_name, blob_name):
    storage_client = storage.Client()

    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.get_blob(blob_name, storage_client)

    return blob.download_as_bytes()


def read_file(file_path: str, mode="rb"):
    with open(file_path, mode=mode) as file:
        data = file.read()
    return data
