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
import datetime as dt

from google import auth
from google.cloud import storage

from flask import Flask, render_template, request
from werkzeug.exceptions import HTTPException

app = Flask(__name__)

CLOUD_STORAGE_BUCKET = os.environ["CLOUD_STORAGE_BUCKET"]
CLOUD_STORAGE_PREFIX = os.environ["CLOUD_STORAGE_PREFIX"]

APP_DETAILS = {
    "title": "Document AI: DSPA Invoices",
}


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
    blob_name = f""
    signed_url = generate_upload_signed_url_v4(
        CLOUD_STORAGE_BUCKET, CLOUD_STORAGE_PREFIX
    )
    return render_template("index.html", signed_url=signed_url)


@app.route("/file_upload", methods=["POST"])
def file_upload() -> str:
    """
    Handle file upload request
    """

    # Check if POST Request includes Files
    if not request.files:
        return render_template("index.html", message_error="No files provided")

    files = request.files.getlist("files")

    uploaded_filenames = save_files_to_temp_directory(files, temp_dir)

    if not uploaded_filenames:
        return render_template("index.html", message_error="No valid files provided")

    status_messages = run_docai_pipeline(uploaded_filenames, FIRESTORE_COLLECTION)

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


def generate_upload_signed_url_v4(bucket_name, blob_name) -> str:
    """Generates a v4 signed URL for uploading a blob using HTTP PUT.

    Note that this method requires a service account key file. You can not use
    this if you are using Application Default Credentials from Google Compute
    Engine or from the Google Cloud SDK.
    """

    credentials, project = auth.default()
    credentials.refresh(auth.transport.requests.Request())

    expiration_timedelta = dt.timedelta(days=1)

    storage_client = storage.Client(credentials=credentials)
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.get_blob(blob_name)

    signed_url = blob.generate_signed_url(
        version="v4",
        expiration=expiration_timedelta,
        service_account_email=credentials.service_account_email,
        access_token=credentials.token,
        method="POST",
    )

    return signed_url


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
