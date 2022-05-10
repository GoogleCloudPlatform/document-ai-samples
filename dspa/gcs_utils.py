# type: ignore[1]
"""
Cloud Storage Utility Functions
"""
import re
import logging

from typing import List, Tuple, Any

from google.cloud import documentai_v1 as documentai
from google.cloud import storage

from consts import (
    BATCH_MAX_FILES,
    ACCEPTED_MIME_TYPES,
    PDF_MIME_TYPE,
)

storage_client = storage.Client()


def split_gcs_uri(gcs_uri: str) -> Tuple[str, str]:
    """
    Split GCS URI into bucket and file path
    GCS API requires the bucket name and URI prefix separately
    """
    matches = re.match(r"gs://([^/]+)/(.+)", gcs_uri)
    if matches:
        return matches.groups()
    logging.error("Invalid GCS URI: %s", gcs_uri)
    return ("", "")


def get_blob_from_gcs(bucket_name: str, object_name: str) -> storage.Blob:
    """
    Get Blob from GCS
    """
    return storage_client.bucket(bucket_name).blob(object_name)


def get_blobs_from_gcs_uri(gcs_uri: str) -> List[storage.Blob]:
    """
    Get Blobs from GCS by URI
    """
    bucket_name, prefix = split_gcs_uri(gcs_uri)
    if not bucket_name or not prefix:
        return []
    return storage_client.list_blobs(bucket_name, prefix=prefix)


def upload_file_to_gcs(
    file_obj: Any, bucket_name: str, object_name: str, mime_type: str = PDF_MIME_TYPE
) -> None:
    """
    Upload file to GCS
    """
    storage_client.bucket(bucket_name).blob(object_name).upload_from_file(
        file_obj, content_type=mime_type
    )


def create_batches(
    input_bucket: str,
    input_prefix: str,
    batch_size: int = BATCH_MAX_FILES,
) -> List[List[documentai.GcsDocument]]:
    """
    Create batches of documents to process
    """
    if batch_size > BATCH_MAX_FILES:
        raise ValueError(
            f"Batch size must be less than {BATCH_MAX_FILES}. "
            f"You provided {batch_size}"
        )

    blob_list = storage_client.list_blobs(input_bucket, prefix=input_prefix)

    batches: List[List[documentai.GcsDocument]] = []
    batch: List[documentai.GcsDocument] = []

    for blob in blob_list:

        if blob.content_type not in ACCEPTED_MIME_TYPES:
            logging.error(
                "Invalid Mime Type %s - Skipping file %s", blob.content_type, blob.name
            )
            continue

        if len(batch) == batch_size:
            batches.append(batch)
            batch = []

        batch.append(
            documentai.GcsDocument(
                gcs_uri=f"gs://{input_bucket}/{blob.name}",
                mime_type=blob.content_type,
            )
        )

    batches.append(batch)
    return batches


def cleanup_gcs(
    input_bucket: str,
    input_prefix: str,
    archive_bucket: str,
):
    """
    Move Input Files to Archive Bucket
    """

    source_bucket = storage_client.bucket(input_bucket)
    destination_bucket = storage_client.bucket(archive_bucket)
    source_blobs = storage_client.list_blobs(input_bucket, prefix=input_prefix)

    for source_blob in source_blobs:
        logging.info("Moving %s to %s", source_blob.name, archive_bucket)
        # Copy input files to archive bucket
        source_bucket.copy_blob(source_blob, destination_bucket, source_blob.name)
        # Delete Original Input Files
        source_blob.delete()
