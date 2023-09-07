# flake8: noqa: E501
# Copyright 2023 Google LLC
# SPDX-License-Identifier: Apache-2.0

import io
import json
from pathlib import Path
from uuid import uuid4

import functions_framework
from google.cloud import storage
from pikepdf import Pdf


@functions_framework.http
def split_document(request):
    """Triggered by Workflow.
    Args:
        request (flask.Request): The request object.
        <https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data>
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`
        <https://flask.palletsprojects.com/en/1.1.x/api/#flask.make_response>.
    """
    request_json = request.get_json(silent=True)
    print(request_json)
    response = request_json
    storage_client = storage.Client()
    input_bucket = storage_client.get_bucket(request_json["resultBucket"])
    input_blob = input_bucket.get_blob(request_json["inputObject"])
    input_content = input_blob.download_as_bytes()
    process_result_bucket = storage_client.get_bucket(request_json["resultBucket"])
    process_result_blob = process_result_bucket.get_blob(request_json["resultObject"])
    process_result_content = process_result_blob.download_as_bytes()
    document = json.loads(process_result_content)
    response["classifications"] = []
    with io.BytesIO(input_content) as pdf_file:
        pdf = Pdf.open(pdf_file)
        for entity in document.get("entities", []):
            output = Pdf.new()
            start_page = min(
                page_ref["page"] for page_ref in entity["page_anchor"]["page_refs"]
            )
            end_page = max(
                page_ref["page"] for page_ref in entity["page_anchor"]["page_refs"]
            )
            for page_ref in entity["page_anchor"]["page_refs"]:
                output.pages.append(pdf.pages[page_ref["page"]])
            file_name = f"{Path(request_json['inputObject']).stem}_{start_page:03d}-{end_page:03d}_{entity['type']}_{uuid4()}.pdf"
            split_blob_name = f"{request_json['resultPrefix']}/{file_name}"
            print(f"Blob name: {split_blob_name}")
            split_blob = process_result_bucket.blob(blob_name=split_blob_name)
            byte_io = io.BytesIO()
            output.save(byte_io)
            split_blob.upload_from_file(
                byte_io, rewind=True, content_type="application/pdf"
            )
            classification = {
                "fileName": file_name,
                "objectName": split_blob_name,
                "pages": end_page - start_page + 1,
                "type": entity["type"],
            }
            response["classifications"].append(classification)
    return response
