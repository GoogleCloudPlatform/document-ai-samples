# Copyright 2022 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Google Cloud Storage Utility Functions"""

import re
import logging
from typing import Set, List, Tuple, Any

from google.cloud.storage import Client, Blob
from google.cloud.documentai_v1 import GcsDocument

from consts import (
    BATCH_MAX_FILES,
    ACCEPTED_MIME_TYPES,
    PDF_MIME_TYPE,
)


_storage_client = Client()


def create_bucket(bucket_name: str, project_id: str, location: str) -> None:
    """
    Create bucket if it does not exist
    """
    bucket = _storage_client.bucket(bucket_name)
    if bucket.exists():
        print(f"Bucket {bucket_name} already exists")
        return

    _storage_client.create_bucket(bucket, project=project_id, location=location)
    print(f"Created bucket {bucket_name}")


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


def create_gcs_uri(bucket_name: str, object_name: str) -> str:
    """
    Create GCS URI
    """
    return f"gs://{bucket_name}/{object_name}"


def get_blob_from_gcs(bucket_name: str, object_name: str) -> Blob:
    """
    Get Blob from GCS
    """
    return _storage_client.bucket(bucket_name).blob(object_name)


def get_blobs_from_gcs_uri(gcs_uri: str) -> List[Blob]:
    """
    Get Blobs from GCS by URI
    """
    bucket_name, prefix = split_gcs_uri(gcs_uri)
    if not bucket_name or not prefix:
        return []
    return _storage_client.list_blobs(bucket_name, prefix=prefix)


def upload_file_to_gcs(
    file_obj: Any, bucket_name: str, object_name: str, mime_type: str = PDF_MIME_TYPE
) -> None:
    """
    Upload file to GCS
    """
    _storage_client.bucket(bucket_name).blob(object_name).upload_from_file(
        file_obj, content_type=mime_type
    )


def create_batches(
    input_bucket: str,
    input_prefix: str,
    batch_size: int = BATCH_MAX_FILES,
) -> List[List[GcsDocument]]:
    """
    Create batches of documents to process
    """
    if batch_size > BATCH_MAX_FILES:
        raise ValueError(
            f"Batch size must be less than {BATCH_MAX_FILES}. "
            f"You provided {batch_size}"
        )

    blob_list = _storage_client.list_blobs(input_bucket, prefix=input_prefix)

    batches: List[List[GcsDocument]] = []
    batch: List[GcsDocument] = []

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
            GcsDocument(
                gcs_uri=create_gcs_uri(input_bucket, blob.name),
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

    source_bucket = _storage_client.bucket(input_bucket)
    destination_bucket = _storage_client.bucket(archive_bucket)
    source_blobs = _storage_client.list_blobs(input_bucket, prefix=input_prefix)

    for source_blob in source_blobs:
        logging.info("Moving %s to %s", source_blob.name, archive_bucket)
        # Copy input files to archive bucket
        source_bucket.copy_blob(source_blob, destination_bucket, source_blob.name)
        # Delete Original Input Files
        source_blob.delete()
