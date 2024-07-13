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

import glob
import io
import shutil
from datetime import datetime
from typing import Optional

import PyPDF2
import google.auth
import google.auth.transport.requests
import requests
from google.cloud import storage

from logging_handler import Logger

logger = Logger.get_logger(__file__)
storage_client = storage.Client()


def get_bearer_token() -> str:
    """Get bearer token through Application Default Credentials."""
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])

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
        with open(file_path, 'rb') as pdf_file:
            pdf_bytes = pdf_file.read()

        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        num_pages = len(reader.pages)
        num_shards = (num_pages + 14) // 15

        pdf_writers = [PyPDF2.PdfWriter() for _ in range(num_shards)]
        for page_index, page in enumerate(reader.pages):
            pdf_writers[page_index // 15].add_page(page)

        for shard_index, pdf_writer in enumerate(pdf_writers):
            output_filename = f"{output_dir}/{file_path[3:-4]} - part {shard_index + 1} of {num_shards}.pdf"
            blob = bucket.blob(output_filename)
            with blob.open("wb", content_type='application/pdf') as output_file:
                pdf_writer.write(output_file)


def get_utc_timestamp() -> str:
    """Get the current UTC timestamp in the format YYYYMMDD_HHMMSSffffff."""
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S%f")


def delete_directory(directory_path: str) -> None:
    """Delete the directory containing the PDF files."""
    try:
        shutil.rmtree(directory_path)
        logger.info(f"Directory '{directory_path}' and its contents removed successfully.")
    except OSError as e:
        logger.info(f"Error removing directory: {e}")
