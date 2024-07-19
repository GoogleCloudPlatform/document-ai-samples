# Copyright 2024 Google LLC
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

# pylint: disable=logging-fstring-interpolation,import-error,broad-exception-caught

"""
Helper functions for interacting with Google Cloud Storage (GCS).

This module includes functions for downloading and uploading files,
adding metadata, retrieving lists of URIs, and writing data to GCS.
"""

import os
from typing import List, Tuple, Dict, Optional

from google.cloud import storage
from google.cloud.documentai_toolbox import gcs_utilities
from logging_handler import Logger
from config import START_PIPELINE_FILENAME, MIME_TYPES, PDF_EXTENSION, SPLITTER_OUTPUT_DIR

logger = Logger.get_logger(__file__)
storage_client = storage.Client()


def download_file(
        gcs_uri: str,
        bucket_name: Optional[str] = None,
        file_to_download: Optional[str] = None,
        output_filename: Optional[str] = "gcs.pdf",
) -> str:
    """
    Downloads a file from a Google Cloud Storage (GCS) bucket to the local directory.

    Args:
      gcs_uri (str): GCS URI of the object/file to download.
      bucket_name (str, optional): Name of the bucket. Defaults to None.
      file_to_download (str, optional): Desired filename in GCS. Defaults to None.
      output_filename (str, optional): Local filename to save the downloaded file.
      Defaults to 'gcs.pdf'.

    Returns:
      str: Local path of the downloaded file.
    """

    if bucket_name is None:
        bucket_name = gcs_uri.split('/')[2]

    # if file to download is not provided it can be extracted from the GCS URI
    if file_to_download is None and gcs_uri is not None:
        file_to_download = '/'.join(gcs_uri.split('/')[3:])

    if output_filename is None:
        _, base_name = split_uri_2_path_filename(gcs_uri)
        output_filename = os.path.join(os.path.dirname(__file__), base_name)

    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(file_to_download)

    with open(output_filename, 'wb') as file_obj:
        blob.download_to_file(file_obj)
        logger.info(f"Downloaded gs://{bucket_name}/{file_to_download} to {output_filename}")

    return output_filename


def add_metadata(gcs_uri: str, metadata: Dict[str, str]):
    """
    Adds custom metadata to a GCS object.

    Args:
      gcs_uri: The full uri to the GCS object.
      metadata: A dictionary containing the metadata key-value pairs to add.
    """
    try:
        bucket_name, blob_name = gcs_utilities.split_gcs_uri(gcs_uri)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        blob.metadata = metadata
        blob.patch()

        logger.info(f"Metadata updated for {blob_name}")
    except Exception as exc:
        logger.error(f"Failed to add metadata to {gcs_uri}: {str(exc)}")


def get_list_of_uris(bucket_name: str, file_uri: str) -> List[str]:
    """Retrieves a list of URIs from a GCS bucket."""
    logger.info(
        f"Getting list of URIs for bucket=[{bucket_name}] and file=[{file_uri}]"
    )
    uri_list: List[str] = []  # Type annotation for uri_list
    if not file_uri:
        logger.warning("No file URI provided")
        return uri_list

    dirs, filename = split_uri_2_path_filename(file_uri)

    if filename != START_PIPELINE_FILENAME:
        # Single File processing
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_uri)
        mime_type = blob.content_type

        if (mime_type and mime_type in MIME_TYPES) or (
                not mime_type and filename.lower().endswith(PDF_EXTENSION.lower())):
            logger.info(f"Handling single file {file_uri}")
            uri_list.append(f"gs://{bucket_name}/{file_uri}")
        else:
            logger.info(f"Skipping {file_uri} - not supported mime type: {mime_type}")
    else:
        # Batch Processing
        logger.info(f"Starting pipeline to process documents inside"
                    f" bucket=[{bucket_name}] and sub-folder=[{dirs}]")
        if dirs is None or dirs == "":
            blob_list = storage_client.list_blobs(bucket_name)
        else:
            blob_list = storage_client.list_blobs(bucket_name, prefix=dirs + "/")

        count = 0
        for blob in blob_list:
            if blob.name and not blob.name.endswith('/') and \
                    blob.name != START_PIPELINE_FILENAME and \
                    not os.path.dirname(blob.name).endswith(SPLITTER_OUTPUT_DIR):
                count += 1
                f_uri = f"gs://{bucket_name}/{blob.name}"
                logger.info(f"Handling {count}(th) document - {f_uri}")
                mime_type = blob.content_type
                if mime_type not in MIME_TYPES:
                    logger.info(f"Skipping {f_uri} - not supported mime type: {mime_type}")
                    continue
                uri_list.append(f_uri)

    return uri_list


def split_uri_2_path_filename(uri: str) -> Tuple[str, str]:
    """
    Splits a URI into directory path and filename.

    Args:
      uri (str): The URI to split.

    Returns:
      Tuple[str, str]: The directory path and filename.
    """

    dirs = os.path.dirname(uri)
    file_name = os.path.basename(uri)
    return dirs, file_name


def upload_file(bucket_name: str, source_file_name: str, destination_blob_name: str) -> str:
    """Uploads a file to the bucket."""
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_file_name)

    output_gcs = f"gs://{bucket_name}/{destination_blob_name}"
    logger.info(f"File {source_file_name} uploaded to {output_gcs}")
    return output_gcs


def write_data_to_gcs(bucket_name: str, blob_name: str, content: str,
                      mime_type: str = "text/plain") -> Tuple[str, str]:
    """
    Writes data to a GCS bucket in the specified format.

    Args:
      bucket_name (str): The name of the GCS bucket.
      blob_name (str): The name of the blob (file) in the bucket.
      content (str): The content to write to the blob.
      mime_type (str, optional): The MIME type of the content. Defaults to "text/plain".

    Returns:
      Tuple[str, str]: The bucket name and blob name.
    """

    logger.info(f"Writing data {content} to gs://{bucket_name}/{blob_name}")

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    blob.upload_from_string(content, content_type=mime_type)

    logger.info(f"Data written to gs://{bucket_name}/{blob_name}")
    return bucket_name, blob_name
