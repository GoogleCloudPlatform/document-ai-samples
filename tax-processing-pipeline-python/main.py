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

# type: ignore
"""Flask Web Server"""

import os
from tempfile import TemporaryDirectory
from typing import List, Tuple
from uuid import uuid4

from consts import FIRESTORE_COLLECTION_PREFIX
from consts import FIRESTORE_PROJECT_ID
from docai_pipeline import run_docai_pipeline
from firestore_utils import delete_collection
from firestore_utils import read_collection
from flask import after_this_request
from flask import Flask
from flask import render_template
from flask import request
from tax_pipeline import calculate_tax_values
from werkzeug.exceptions import HTTPException

SESSION_ID = str(uuid4())
FIRESTORE_COLLECTION = f"{FIRESTORE_COLLECTION_PREFIX}-{SESSION_ID}"

app = Flask(__name__)

UPLOAD_FOLDER = "/tmp"
ALLOWED_MIMETYPES = set(["application/pdf", "image/tiff", "image/jpeg"])


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
    # pylint: disable=consider-using-with
    temp_dir = TemporaryDirectory()

    @after_this_request
    def cleanup(response):
        temp_dir.cleanup()
        return response

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


@app.route("/view_extracted_data", methods=["GET"])
def view_extracted_data() -> str:
    """
    Display Raw extracted data from Documents
    """
    extracted_data = read_collection(FIRESTORE_PROJECT_ID, FIRESTORE_COLLECTION)
    if not extracted_data:
        return render_template("index.html", message_error="No data to display")
    return render_template("index.html", extracted_data=extracted_data)


@app.route("/view_tax_bill", methods=["GET"])
def view_tax_bill() -> str:
    """
    Calculate Tax Return with Document Information from Firestore
    """
    extracted_data = read_collection(FIRESTORE_PROJECT_ID, FIRESTORE_COLLECTION)
    tax_data = calculate_tax_values(extracted_data)

    if not tax_data:
        return render_template("index.html", message_error="No data to display")
    return render_template("index.html", tax_data=tax_data)


@app.route("/delete_data", methods=["GET"])
def delete_data() -> str:
    """
    Remove Saved Data from Database
    """
    delete_collection(FIRESTORE_PROJECT_ID, FIRESTORE_COLLECTION)
    return render_template("index.html", message_success="Successfully deleted data")


def save_files_to_temp_directory(files, temp_dir) -> List[Tuple[str, str]]:
    """
    Save files to temporary directory
    Returns a list of tuples containing file paths and mimetypes
    """
    uploaded_filenames: List[Tuple[str, str]] = []
    for file in files:
        if not file or file.filename == "":
            print("Skipping corrupt file")
            continue

        if file.mimetype not in ALLOWED_MIMETYPES:
            print(f"Invalid File Type: {file.filename}: {file.mimetype}")
            continue

        input_file_path = os.path.join(temp_dir.name, file.filename)
        file.save(input_file_path)
        uploaded_filenames.append((input_file_path, file.mimetype))
        print(f"Uploaded file: {input_file_path}, {file.mimetype}")

    return uploaded_filenames


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
        message_error="An unknown error occurred, please try again later",
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
