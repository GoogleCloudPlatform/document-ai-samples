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

# type: ignore[1]
"""Flask Web Server"""

import os
from typing import List, Any

from google.cloud import storage

from flask import Flask, render_template, request
from werkzeug.exceptions import HTTPException

app = Flask(__name__)

CLOUD_STORAGE_BUCKET = os.environ["CLOUD_STORAGE_BUCKET"]
CLOUD_STORAGE_PREFIX = os.environ["CLOUD_STORAGE_PREFIX"]
PROJECT_ID = os.environ["PROJECT_ID"]

PDF_MIME_TYPE = "application/pdf"
ACCEPTED_MIME_TYPES = set({PDF_MIME_TYPE})

APP_DETAILS = {
    "title": "Document AI: DSPA Invoices",
}

storage_client = storage.Client(project=PROJECT_ID)


def upload_file_to_gcs(
    file_obj: Any, bucket_name: str, object_name: str, mime_type: str
) -> None:
    """
    Upload file to GCS
    """
    storage_client.bucket(bucket_name).blob(object_name).upload_from_file(
        file_obj, content_type=mime_type
    )


@app.context_processor
def app_details():
    """
    Add app details to template context
    """
    return APP_DETAILS


@app.route("/", methods=["GET"])
def index() -> str:
    """
    Web Server, Homepage
    """
    return render_template("index.html")


@app.route("/file_upload", methods=["POST"])
def file_upload() -> str:
    """
    Handle file upload request
    """

    # Check if POST Request includes Files
    if not request.files:
        return render_template("index.html", message_error="No files provided")

    files = request.files.getlist("files")

    status_messages: List[str] = []

    for file in files:
        if file.content_type not in ACCEPTED_MIME_TYPES:
            status_messages.append(
                f"Unable to process file: {file.filename} - Invalid Mime Type: {file.content_type}"
            )
            continue

        upload_file_to_gcs(
            file.stream,
            bucket_name=CLOUD_STORAGE_BUCKET,
            object_name=f"{CLOUD_STORAGE_PREFIX}/{file.filename}",
            mime_type=file.content_type,
        )

    return render_template(
        "index.html",
        message_success="Successfully uploaded & processed files",
        status_messages=status_messages,
    )


@app.errorhandler(Exception)
def handle_exception(ex):
    """
    Handle Application Exceptions
    """
    # Pass through HTTP errors
    if isinstance(ex, HTTPException):
        return ex

    # Non-HTTP exceptions only
    return render_template(
        "index.html",
        message_error=str(ex),
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
