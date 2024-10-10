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

# pylint: disable=logging-fstring-interpolation,import-error

"""
Utility functions  for obtaining authentication tokens,
sending callback requests, splitting PDF files into multiple parts,
getting the current UTC timestamp, and deleting directories.
"""

from datetime import datetime
import glob
import io
import shutil
from typing import Optional

import google.auth
import google.auth.transport.requests
from google.cloud import storage
from logging_handler import Logger
import PyPDF2
import requests

logger = Logger.get_logger(__file__)
storage_client = storage.Client()


def get_bearer_token() -> str:
    """Get bearer token through Application Default Credentials."""
    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    # creds.valid is False, and creds.token is None
    # Need to refresh credentials to populate those
    auth_req = google.auth.transport.requests.Request()
    creds.refresh(auth_req)
    return creds.token


def send_callback_request(callback_url: Optional[str], payload: dict) -> None:
    """Send a callback request with the given payload to the specified URL."""
    if not callback_url:
        logger.warning("No callback URL provided")
        return

    logger.info(f"Calling {callback_url} with payload {payload}")
    headers = {
        "Authorization": f"Bearer {get_bearer_token()}",
        "Content-Type": "application/json",
    }

    response = requests.post(callback_url, headers=headers, json=payload)

    if response.status_code == 200:
        logger.info("Callback successful")
    else:
        logger.error(f"Callback failed: {response.status_code} - {response.text}")


def split_pages(file_pattern: str, bucket_name: str, output_dir: str) -> None:
    """Split a PDF file into parts with up to 15 pages and upload the parts to GCS."""
    bucket = storage_client.bucket(bucket_name)
    for file_path in glob.glob(file_pattern):
        split_and_upload_pdf(file_path, bucket, output_dir)


def split_and_upload_pdf(
    file_path: str, bucket: storage.Bucket, output_dir: str
) -> None:
    """Split a single PDF file into parts and upload the parts to GCS."""
    pdf_bytes = read_pdf_file(file_path)
    reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
    num_pages = len(reader.pages)
    num_shards = (num_pages + 14) // 15

    for shard_index in range(num_shards):
        pdf_writer = PyPDF2.PdfWriter()
        add_pages_to_writer(reader, pdf_writer, shard_index, num_pages)
        output_filename = generate_output_filename(
            file_path, output_dir, shard_index, num_shards
        )
        upload_pdf(bucket, pdf_writer, output_filename)


def read_pdf_file(file_path: str) -> bytes:
    """Read a PDF file and return its content as bytes."""
    with open(file_path, "rb") as pdf_file:
        return pdf_file.read()


def add_pages_to_writer(
    reader: PyPDF2.PdfReader, writer: PyPDF2.PdfWriter, shard_index: int, num_pages: int
) -> None:
    """Add pages to the PDF writer for a specific shard."""
    for page_index in range(15):
        page_number = shard_index * 15 + page_index
        if page_number < num_pages:
            writer.add_page(reader.pages[page_number])


def generate_output_filename(
    file_path: str, output_dir: str, shard_index: int, num_shards: int
) -> str:
    """Generate the output filename for a PDF shard."""
    return (
        f"{output_dir}/{file_path[3:-4]} - part {shard_index + 1} of {num_shards}.pdf"
    )


def upload_pdf(
    bucket: storage.Bucket, writer: PyPDF2.PdfWriter, output_filename: str
) -> None:
    """Upload the PDF writer content to GCS."""
    blob = bucket.blob(output_filename)
    with blob.open("wb", content_type="application/pdf") as output_file:
        writer.write(output_file)


def get_utc_timestamp() -> str:
    """Get the current UTC timestamp in the format YYYYMMDD_HHMMSSffffff."""
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S%f")


def delete_directory(directory_path: str) -> None:
    """Delete the directory containing the PDF files."""
    try:
        shutil.rmtree(directory_path)
        logger.info(
            f"Directory '{directory_path}' and its contents removed successfully."
        )
    except OSError as e:
        logger.info(f"Error removing directory: {e}")
