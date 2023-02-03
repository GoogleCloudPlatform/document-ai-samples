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
from google.cloud.documentai_v1beta3 import Document
from google.cloud.documentai_v1beta3 import DocumentProcessorServiceClient
from google.cloud.documentai_v1beta3 import ListProcessorsRequest
from google.cloud.documentai_v1beta3 import ProcessRequest
from google.cloud.documentai_v1beta3 import ProcessResponse


def process_document(process_document_request):
    """Handles Document AI API call and returns the document proto as JSON"""

    project_id = process_document_request["project_id"]
    location = process_document_request["location"]
    file_path = process_document_request["file_path"]
    file_type = process_document_request["file_type"]
    processor_id = process_document_request["processor_id"]

    # Instantiates a client
    client = DocumentProcessorServiceClient()

    # The full resource name of the processor, e.g.:
    # projects/project-id/locations/location/processor/processor-id
    # You must create new processors in the Cloud Console first
    name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

    # TODO : change file handling if the file that was sent in the request is stored in GCS # pylint: disable=W0511
    with open(file_path, "rb") as pdf:
        pdf_content = pdf.read()

    # Read the file into memory
    document = Document()
    document.content = pdf_content
    document.mime_type = file_type

    # Configure the process request
    request = ProcessRequest()
    request.name = name
    request.document = document

    # Use the Document AI client to process the sample form
    try:
        result = client.process_document(request=request)
    except Exception as err:  # pylint: disable=W0703
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
    client = DocumentProcessorServiceClient()

    req = ListProcessorsRequest()
    req.parent = f"projects/{project_id}/locations/{location}"

    try:
        processor_list = client.list_processors(req)

        for processor in processor_list:
            # The resource name of the processor follows the following
            # format `projects/{project}/locations/{location}/processors/{processor}`
            parsed_path = client.parse_processor_path(processor.name)
            processor_id_by_processor_type[processor.type_] = parsed_path["processor"]
    except Exception as err:  # pylint: disable=W0703
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
