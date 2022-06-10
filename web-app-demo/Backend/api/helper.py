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

""" Helper file that holds DocAI API calls"""
from typing import List, Dict

from google.api_core.client_options import ClientOptions
from google.cloud.documentai_v1 import (
    DocumentProcessorServiceClient,
    Document,
    ProcessRequest,
    ProcessResponse,
)

# v1 API doesn't support processor Management Functions
import google.cloud.documentai_v1beta3 as docai_beta3


def process_document(process_document_request: Dict) -> str:
    """Handles Document AI API call and returns the document proto as JSON"""

    location = process_document_request["location"]
    file_path = process_document_request["file_path"]
    file_type = process_document_request["file_type"]
    processor_name = process_document_request["processor_name"]

    # Instantiates a client
    client = DocumentProcessorServiceClient(
        client_options=ClientOptions(
            api_endpoint=f"{location}-documentai.googleapis.com"
        )
    )

    # TODO : change file handling if the file that was sent in the request is stored in GCS # pylint: disable=fixme
    with open(file_path, "rb") as pdf:
        pdf_content = pdf.read()

    # Read the file into memory
    document = Document(content=pdf_content, mime_type=file_type)

    # Configure the process request
    request = ProcessRequest(name=processor_name, inline_document=document)

    try:
        result = client.process_document(request=request)
    except Exception as err:  # pylint: disable=broad-except
        return str(err)

    document = result.document

    json_result = ProcessResponse.to_json(result, including_default_value_fields=False)

    return json_result


# TODO: Store the file that was sent in the request in GCS # pylint: disable=fixme


def store_file(directory, file) -> str:
    """Stores the file to specified destination"""
    destination = f"{directory}/{file.name}"
    file.save(destination)
    return destination


def get_processors(project_id, location) -> List[Dict]:
    """Gets all available processors from the specified GCP project"""

    if location == "ENTER_YOUR_LOCATION_HERE":
        print("Location was not changed")
        return []

    client = docai_beta3.DocumentProcessorServiceClient(
        client_options=ClientOptions(
            api_endpoint=f"{location}-documentai.googleapis.com"
        )
    )

    parent = client.common_location_path(project_id, location)
    req = docai_beta3.ListProcessorsRequest(parent=parent)

    # Transforming Pager into List
    processor_list: List[Dict] = []
    try:
        list_processors_pager = client.list_processors(req)
        for processor in list_processors_pager:
            processor_list.append(
                docai_beta3.Processor.to_dict(
                    processor, preserving_proto_field_name=False
                )
            )
        return processor_list
    except Exception as err:  # pylint: disable=broad-except
        print(f"Error: {err}")
        return []
