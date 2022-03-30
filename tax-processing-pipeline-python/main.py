"""
Flask Web Server
"""
import os

from tempfile import TemporaryDirectory
from typing import List, Tuple
from flask import Flask, after_this_request, render_template, request
from werkzeug.exceptions import HTTPException

from docai_pipeline import run_docai_pipeline
from tax_pipeline import run_tax_pipeline, get_stored_data

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
        return render_template(
            "index.html", message_error="No valid files provided"
        )

    run_docai_pipeline(uploaded_filenames)

    return render_template(
        "index.html", message_success="Successfully uploaded files"
    )


@app.route("/view_extracted_data", methods=["GET"])
def view_extracted_data() -> str:
    """
    Display Raw extracted data from Documents
    """
    extracted_data = get_stored_data()
    if not extracted_data:
        return render_template(
            "index.html", message_error="No data to display"
        )
    return render_template("index.html", extracted_data=extracted_data)


@app.route("/view_data_aggregation", methods=["GET"])
def view_data_aggregation() -> str:
    """
    Calculate Tax Return with Document Information from Firestore
    """
    tax_data = run_tax_pipeline()
    if not tax_data:
        return render_template(
            "index.html", message_error="No data to display"
        )
    return render_template("index.html", tax_data=tax_data)


def save_files_to_temp_directory(files, temp_dir) -> List[Tuple[str, str]]:
    """
    Save files to temporary directory
    Returns a list of tuples containing file paths and mimetypes
    """
    uploaded_filenames = []
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
def handle_exception(e):
    """
    Handle Application Exceptions
    """
    # pass through HTTP errors
    if isinstance(e, HTTPException):
        return e

    # now you're handling non-HTTP exceptions only
    return render_template(
        "index.html",
        message_error="An unknown error occurred, please try again later",
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
