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
import logging
from typing import Dict, List

from google.api_core.client_options import ClientOptions
from google.protobuf.json_format import ParseError

from google.cloud import documentai_v1 as documentai

from consts import (
    DEFAULT_PROJECT_ID,
    DEFAULT_LOCATION,
    BATCH_MAX_FILES,
    TIMEOUT,
    ACCEPTED_MIME_TYPES,
    SKIP_HUMAN_REVIEW,
)

from gcs_utils import get_blobs_from_gcs_uri

docai_client = documentai.DocumentProcessorServiceClient(
    client_options=ClientOptions(
        api_endpoint=f"{DEFAULT_LOCATION}-documentai.googleapis.com"
    )
)


def extract_document_entities(document: documentai.Document) -> dict:
    """
    Get all entities from a document and output as a dictionary
    Flattens nested entities/properties
    Format: entity.type_: entity.mention_text OR entity.normalized_value.text
    """
    document_entities: Dict[str, str] = {}

    for entity in document.entities:

        entity_key = entity.type_.replace("/", "_")
        normalized_value = getattr(entity, "normalized_value", None)

        entity_value = (
            normalized_value.text if normalized_value else entity.mention_text
        )

        document_entities.update({entity_key: entity_value})

    document_entities.update({"input_filename": document.uri})

    return document_entities


def online_process(
    processor_name: str,
    file_path: str = None,
    mime_type: str = None,
    inline_document: documentai.Document = None,
    skip_human_review: bool = SKIP_HUMAN_REVIEW,
) -> documentai.Document:
    """
    Use Online processing on single document
    """
    # Process Raw File
    if file_path and mime_type:
        if mime_type not in ACCEPTED_MIME_TYPES:
            logging.error("File %s is unsupported MIME Type: %s", file_path, mime_type)
            return documentai.Document()

        with open(file_path, "rb") as image:
            request = documentai.ProcessRequest(
                name=processor_name,
                raw_document=documentai.RawDocument(
                    content=image.read(),
                    mime_type=mime_type,
                ),
                skip_human_review=skip_human_review,
            )
    # Process Document Object
    elif inline_document:
        request = documentai.ProcessRequest(
            name=processor_name,
            inline_document=inline_document,
            skip_human_review=skip_human_review,
        )
    else:
        logging.error("No file or document object provided")
        return documentai.Document()

    result = docai_client.process_document(request=request)

    return result.document


def batch_process(
    processor_name: str,
    document_batch: List[documentai.GcsDocument],
    gcs_output_uri: str,
    skip_human_review: bool = SKIP_HUMAN_REVIEW,
) -> documentai.BatchProcessMetadata:
    """
    Constructs requests to process documents using the Document AI
    Batch Method.
    Returns Batch Process Metadata
    """

    output_config = documentai.DocumentOutputConfig(
        gcs_output_config=documentai.DocumentOutputConfig.GcsOutputConfig(
            gcs_uri=gcs_output_uri
        )
    )

    # Load GCS Input URI into a List of document files
    input_config = documentai.BatchDocumentsInputConfig(
        gcs_documents=documentai.GcsDocuments(documents=document_batch)
    )
    request = documentai.BatchProcessRequest(
        name=processor_name,
        input_documents=input_config,
        document_output_config=output_config,
        skip_human_review=skip_human_review,
    )

    operation = docai_client.batch_process_documents(request)

    # The API supports limited concurrent requests.
    logging.info("Waiting for operation %s to complete...", operation.operation.name)
    # No Timeout Set
    operation.result()

    return documentai.BatchProcessMetadata(operation.metadata)


def get_batch_process_output(
    metadata: documentai.BatchProcessMetadata,
) -> List[documentai.Document]:
    """
    Retrieve Document Objects from GCS after Batch Processing
    """

    if metadata.state != documentai.BatchProcessMetadata.State.SUCCEEDED:
        logging.error("Batch Process failed: %s", metadata.state_message)
        return []

    documents: List[documentai.Document] = []

    # Should be one process for each source file
    for process in metadata.individual_process_statuses:
        # URI: gs://BUCKET/PREFIX/OPERATION_NUMBER/0
        # Trailing "/" added to prevent "/1/" "/10/" ambiguity
        blobs = get_blobs_from_gcs_uri(f"{process.output_gcs_destination}/")

        # DocAI may output multiple JSON files per source file
        for blob in blobs:
            # Document AI should only output JSON files to GCS
            if ".json" not in blob.name:
                logging.error("Skipping non-json file: %s", blob.name)
                continue
            try:
                print("Fetching from " + blob.name)
                output_document = documentai.types.Document.from_json(
                    blob.download_as_bytes(), ignore_unknown_fields=True
                )

                # Save Source File URI to Document Object
                output_document.uri = process.input_gcs_source
                documents.append(output_document)
            except ParseError:
                logging.error("Failed to parse: %s", blob.name)
                continue

    return documents
