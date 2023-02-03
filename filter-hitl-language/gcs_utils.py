"""
Google Cloud Storage Functions
"""
from typing import Any, Set

from google.cloud import storage

storage_client = storage.Client()


def get_files_from_gcs(gcs_bucket: str, gcs_prefix: str) -> Any:
    """
    Get List of GCS Files
    """
    return storage_client.list_blobs(gcs_bucket, prefix=gcs_prefix)


def create_bucket(bucket_name: str) -> None:
    """
    Create bucket if it does not exist
    """
    bucket = storage_client.bucket(bucket_name)
    if not bucket.exists():
        storage_client.create_bucket(bucket)


def get_all_buckets() -> Set[str]:
    """
    Get all buckets
    """
    buckets = storage_client.list_buckets()
    return set({bucket.name for bucket in buckets})


def move_file(
    source_bucket_name: str, input_filename: str, destination_bucket_name: str
) -> None:
    """
    Move file from one bucket to another
    """
    print(
        f"Moving {input_filename} from {source_bucket_name} to {destination_bucket_name}\n"
    )
    source_bucket = storage_client.bucket(source_bucket_name)
    source_blob = source_bucket.blob(input_filename)
    destination_bucket = storage_client.bucket(destination_bucket_name)

    source_bucket.copy_blob(source_blob, destination_bucket)
    # Uncomment the following line to delete the source blob
    # source_bucket.delete_blob(input_filename)
