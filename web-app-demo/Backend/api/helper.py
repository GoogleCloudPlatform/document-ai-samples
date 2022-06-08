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
# pylint: disable-msg=too-many-locals

""" Helper file that holds DocAI API calls"""
from google.cloud.documentai_v1 import (
    DocumentProcessorServiceClient,
    Document,
    ProcessRequest,
    ProcessResponse,
)

# v1 API doesn't support processor Management Functions
import google.cloud.documentai_v1beta3 as docai_beta3

from google.api_core.client_options import ClientOptions


def process_document(process_document_request, processor_id_by_processor_type):
    """Handles Document AI API call and returns the document proto as JSON"""

    project_id = process_document_request["project_id"]
    location = process_document_request["location"]
    file_path = process_document_request["file_path"]
    file_type = process_document_request["file_type"]
    processor_type = process_document_request["processor_type"]

    if processor_id_by_processor_type == []:
        populate_list_source(project_id, location, processor_id_by_processor_type)

    print(processor_id_by_processor_type)

    processor_id = processor_id_by_processor_type[processor_type]

    # Instantiates a client
    client = DocumentProcessorServiceClient(
        client_options=ClientOptions(
            api_endpoint=f"{location}-documentai.googleapis.com"
        )
    )

    # The full resource name of the processor, e.g.:
    # projects/project-id/locations/location/processor/processor-id
    # You must create new processors in the Cloud Console first
    name = client.processor_path(project_id, location, processor_id)

    # TODO : change file handling if the file that was sent in the request is stored in GCS # pylint: disable=fixme
    with open(file_path, "rb") as pdf:
        pdf_content = pdf.read()

    # Read the file into memory
    document = Document(content=pdf_content, mime_type=file_type)

    # Configure the process request
    request = ProcessRequest(name=name, inline_document=document)

    try:
        result = client.process_document(request=request)
    except Exception as err:  # pylint: disable=broad-except
        return {
            "resultStatus": "ERROR",
            "errorMessage": str(err),
        }

    document = result.document

    json_result = ProcessResponse.to_json(result)

    return json_result


# TODO: Store the file that was sent in the request in GCS # pylint: disable=W0511


def store_file(file):
    """Stores the file to specified destination"""
    destination = "/".join(["api/test_docs", file.name])
    file.save(destination)
    return destination


def populate_list_source(project_id, location, processor_id_by_processor_type):
    """Gets all available processors from the specified GCP project"""
    client = docai_beta3.DocumentProcessorServiceClient(
        client_options=ClientOptions(
            api_endpoint=f"{location}-documentai.googleapis.com"
        )
    )

    parent = client.common_location_path(project_id, location)
    req = docai_beta3.ListProcessorsRequest(parent=parent)

    try:
        processor_list = client.list_processors(req)

        for processor in processor_list:
            # The resource name of the processor follows the following
            # format `projects/{project}/locations/{location}/processors/{processor}`
            parsed_path = client.parse_processor_path(processor.name)
            processor_id_by_processor_type[processor.type_] = parsed_path["processor"]
    except Exception as err:  # pylint: disable=broad-except
        if location == "ENTER_YOUR_LOCATION_HERE":
            str_error = "Location was not changed"
        else:
            str_error = str(err)
        return {
            "resultStatus": "ERROR",
            "errorMessage": str_error,
        }, 400
    return {
        "resultStatus": "SUCCESS",
    }
