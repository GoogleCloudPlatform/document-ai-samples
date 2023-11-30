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

"""Document AI Utility Functions"""

from typing import Dict, List, Optional, Sequence, Tuple

from consts import CLASSIFIER_PROCESSOR_TYPES
from consts import DEFAULT_MIME_TYPE
from consts import DOCAI_ACTIVE_PROCESSORS
from consts import DOCAI_PROCESSOR_LOCATION
from consts import DOCAI_PROJECT_ID
from consts import DOCUMENT_SUPPORTED_PROCESSOR_TYPES
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai

client_options = ClientOptions(
    api_endpoint=f"{DOCAI_PROCESSOR_LOCATION}-documentai.googleapis.com"
)

# Instantiates a client
documentai_client = documentai.DocumentProcessorServiceClient(
    client_options=client_options
)


def process_document(
    project_id: str,
    location: str,
    processor_id: str,
    file_content: Optional[bytes] = None,
    inline_document: Optional[documentai.Document] = None,
    mime_type: str = DEFAULT_MIME_TYPE,
) -> documentai.Document:
    """
    Processes a document using the Document AI API.
    Takes in bytes from file reading, instead of a file path
    """
    # The full resource name of the processor, e.g.:
    # projects/project-id/locations/location/processor/processor-id
    # You must create new processors in the Cloud Console first
    resource_name = documentai_client.processor_path(project_id, location, processor_id)

    # Configure the process request
    request = documentai.ProcessRequest(name=resource_name)

    if file_content:
        # Load Binary Data into Document AI RawDocument Object
        request.raw_document = documentai.RawDocument(
            content=file_content, mime_type=mime_type
        )
    elif inline_document:
        request.inline_document = inline_document
    else:
        return None
    # Use the Document AI client to process the sample form
    result = documentai_client.process_document(request=request)
    return result.document


def extract_document_entities(document: documentai.Document) -> Dict[str, str]:
    """
    Get all entities from a document and output as a dictionary
    Format: entity.type_: entity.mention_text OR entity.normalized_value.text
    """
    # For a full list of fields for each processor see
    # the processor documentation:
    # https://cloud.google.com/document-ai/docs/processors-list
    # Use EKG Enriched Data if available
    return {
        entity.type_: entity.normalized_value.text
        if hasattr(entity, "normalized_value")
        else entity.mention_text
        for entity in document.entities
    }


def select_processor_from_classification(
    document_classification: str = "other",
) -> Tuple[str, str]:
    """
    Select Processor for a given Document Classification
    """

    # Get Supported Parser Processor Type from Document Classification
    processor_type = DOCUMENT_SUPPORTED_PROCESSOR_TYPES.get(
        document_classification, "FORM_PARSER_PROCESSOR"
    )

    # Get Specific Processor ID for this Parser Type
    processor_id = DOCAI_ACTIVE_PROCESSORS.get(processor_type)

    return processor_type, processor_id


def classify_document(file_content: bytes, mime_type: str) -> str:
    """
    Classify a single document with all available specialized processors
    """

    # Cycle through all possible classifier Processor Types
    for classifier_processor_type in CLASSIFIER_PROCESSOR_TYPES:
        # Get Specific Processor ID for this Classifier Type
        classifier_processor_id = DOCAI_ACTIVE_PROCESSORS.get(classifier_processor_type)
        if not classifier_processor_id:
            continue

        # Classify Document
        classification_document_proto = process_document(
            DOCAI_PROJECT_ID,
            DOCAI_PROCESSOR_LOCATION,
            classifier_processor_id,
            file_content=file_content,
            mime_type=mime_type,
        )
        # Translate Classification Output to Processor Type
        document_classification = classification_document_proto.entities[0].type_

        # Specialized Classifiers return "other"
        # if it could not classify to a known type
        if document_classification == "other":
            continue

    return document_classification


def get_processor_id(path: str):
    """
    Extract Processor ID (Hexadecimal Number) from full processor path
    """
    return documentai_client.parse_processor_path(path)["processor"]


def fetch_processor_types(
    project_id: str, location: str
) -> Sequence[documentai.ProcessorType]:
    """
    Returns a list of processor types enabled for the given project.
    """
    response = documentai_client.fetch_processor_types(
        parent=documentai_client.common_location_path(project_id, location)
    )
    return response.processor_types


def create_processor(
    project_id: str, location: str, display_name: str, processor_type: str
) -> documentai.Processor:
    """
    Creates a new processor.
    """
    processor_info = documentai.Processor(
        display_name=display_name, type_=processor_type
    )
    return documentai_client.create_processor(
        parent=documentai_client.common_location_path(project_id, location),
        processor=processor_info,
    )


def list_processors(project_id: str, location: str) -> List[documentai.Processor]:
    """Lists existing processors."""
    return list(
        documentai_client.list_processors(
            parent=documentai_client.common_location_path(project_id, location),
        )
    )
