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
from typing import Dict, List, Tuple, Sequence

from google.api_core.operation import Operation
from google.api_core.client_options import ClientOptions
from google.protobuf.json_format import ParseError

from google.cloud.documentai_v1 import (
    Document,
    DocumentProcessorServiceClient,
    ProcessRequest,
    RawDocument,
    BatchProcessMetadata,
    DocumentOutputConfig,
    BatchProcessRequest,
    BatchDocumentsInputConfig,
    GcsDocument,
    GcsDocuments,
    GcsPrefix,
)

# As of June 2022, only the v1beta3 Client Library supports processor management
from google.cloud.documentai_v1beta3 import (
    DocumentProcessorServiceClient as BetaDocumentProcessorServiceClient,
    ProcessorType,
    Processor,
)

from consts import (
    CONFIDENCE_THRESHOLD,
    DEFAULT_PROJECT_ID,
    DEFAULT_LOCATION,
    JSON_MIME_TYPE,
    TIMEOUT,
    ACCEPTED_MIME_TYPES,
    SKIP_HUMAN_REVIEW,
)

from gcs_utils import get_blobs_from_gcs_uri

_client_options = ClientOptions(
    api_endpoint=f"{DEFAULT_LOCATION}-documentai.googleapis.com"
)


def _extract_entity(
    entity: Document.Entity, entity_dict: Dict[str, str], delimeter: str = None
) -> Dict[str, str]:
    """
    Extract Entity Type & Value
    """
    if delimeter:
        # "/" is not allowed in BigQuery
        entity_key = entity.type_.replace("/", delimeter)
    else:
        entity_key = entity.type_

    # Use normalized_value if available
    normalized_value = getattr(entity, "normalized_value", None)
    entity_value = normalized_value.text if normalized_value else entity.mention_text

    entity_dict[entity_key] = entity_value
    return entity_dict


def extract_document_entities(document: Document) -> Dict[str, str]:
    """
    Get all entities from a document and output as a dictionary
    Flattens nested entities/properties
    Format: entity.type_: entity.mention_text OR entity.normalized_value.text
    """
    entity_dict: Dict[str, str] = {}

    for entity in document.entities:
        _extract_entity(entity, entity_dict)
        # "property" is a reserved word
        for prop in entity.properties:
            _extract_entity(prop, entity_dict)

    return entity_dict


def extract_subdocuments(document: Document) -> List[Tuple[str, List[int]]]:
    """
    Extract Classifications/Split Points from Splitter/Classifier Output Document
    [
        {type_: [page_nums]},
        {type_: [page_nums]},
    ]
    """
    subdocs: List[Tuple[str, List[int]]] = []

    # Extract SubDocuments for each entity
    for entity in document.entities:
        subdoc: Tuple[str, List[int]] = entity.type_, []
        # Get Page Range for SubDocument
        for page_ref in entity.page_anchor.page_refs:
            subdoc[1].append(int(page_ref.page))

        subdocs.append(subdoc)

    return subdocs


def _extract_form_fields(document: Document) -> List[Document.Page.FormField]:
    """
    Get FormFields from Form Parser output Document
    """
    form_fields: List[Document.Page.FormField] = []

    for page in document.pages:
        for form_field in page.form_fields:
            form_fields.append(form_field)
    return form_fields


def get_form_data_dictionary(document: Document) -> Dict[str, str]:
    """
    Get Key/Value Pairs from Form Parser Output Document
    """
    form_data: Dict[str, str] = {}

    form_fields = _extract_form_fields(document)

    for form_field in form_fields:
        # TODO: Check on form_field.value_type for checkboxes
        field_name = form_field.field_name.text_anchor.content
        field_value = form_field.field_value.text_anchor.content
        form_data[field_name] = field_value

    return form_data


def _create_entity_from_form_field(
    form_field: Document.Page.FormField, entity_id: int
) -> Document.Entity:
    """
    Extract FormField Data and Load into Entity
    """
    field_name: Document.Page.Layout = form_field.field_name
    field_value: Document.Page.Layout = form_field.field_value

    if (
        field_name.confidence < CONFIDENCE_THRESHOLD
        or field_value.confidence < CONFIDENCE_THRESHOLD
    ):
        logging.warning(
            "Form Field %s: %s has low confidence (%.2f, %.2f). Not Converting to Entity",
            field_name.text_anchor.content,
            field_value.text_anchor.content,
            field_name.confidence,
            field_value.confidence,
        )
        return Document.Entity()

    page_anchor = Document.PageAnchor(
        page_refs=[Document.PageAnchor.PageRef(bounding_poly=field_value.bounding_poly)]
    )

    return Document.Entity(
        text_anchor=field_value.text_anchor,
        type_=field_name.text_anchor.content,
        mention_text=field_value.text_anchor.content,
        confidence=field_value.confidence,
        page_anchor=page_anchor,
        id=str(entity_id),
    )


def transform_form_fields_to_entities(document: Document) -> Document:
    """
    Converts FormField to Entities in Document
    """
    entities: List[Document.Entity] = []
    form_fields = _extract_form_fields(document)

    for index, form_field in enumerate(form_fields):
        entities.append(_create_entity_from_form_field(form_field, index))

    document.entities = entities
    return document


def online_process(
    processor_name: str,
    file_path: str = None,
    mime_type: str = None,
    inline_document: Document = None,
    skip_human_review: bool = SKIP_HUMAN_REVIEW,
) -> Document:
    """
    Use Online processing on single document
    """
    docai_client = DocumentProcessorServiceClient(client_options=_client_options)

    # Process Raw File
    if file_path and mime_type:
        if mime_type not in ACCEPTED_MIME_TYPES:
            logging.error("File %s is unsupported MIME Type: %s", file_path, mime_type)
            return Document()

        with open(file_path, "rb") as image:
            request = ProcessRequest(
                name=processor_name,
                raw_document=RawDocument(
                    content=image.read(),
                    mime_type=mime_type,
                ),
                skip_human_review=skip_human_review,
            )
    # Process Document Object
    elif inline_document:
        request = ProcessRequest(
            name=processor_name,
            inline_document=inline_document,
            skip_human_review=skip_human_review,
        )
    else:
        logging.error("No file or document object provided")
        return Document()

    result = docai_client.process_document(request=request)

    return result.document


def batch_process_list(
    processor_name: str,
    document_batch: List[GcsDocument],
    gcs_output_uri: str,
    skip_human_review: bool = SKIP_HUMAN_REVIEW,
) -> Operation:
    """
    Calls Batch Process Method with a list of GCS URIs
    Returns BatchProcessMetadata
    """
    # Load GCS Input URI into a List of document files
    input_config = BatchDocumentsInputConfig(
        gcs_documents=GcsDocuments(documents=document_batch)
    )
    return _batch_process(
        processor_name, input_config, gcs_output_uri, skip_human_review
    )


def batch_process_directory(
    processor_name: str,
    gcs_input_uri: str,
    gcs_output_uri: str,
    skip_human_review: bool = SKIP_HUMAN_REVIEW,
) -> Operation:
    """
    Calls Batch Process Method with a GCS URI Prefix
    Returns BatchProcessMetadata
    """
    # Load GCS Prefix into InputConfig
    input_config = BatchDocumentsInputConfig(
        gcs_prefix=GcsPrefix(gcs_uri_prefix=gcs_input_uri)
    )
    return _batch_process(
        processor_name, input_config, gcs_output_uri, skip_human_review
    )


def _batch_process(
    processor_name: str,
    input_config: BatchDocumentsInputConfig,
    gcs_output_uri: str,
    skip_human_review: bool = SKIP_HUMAN_REVIEW,
) -> Operation:
    """
    Internal Method for constructing Batch Process Requests
    Returns Batch Process Metadata
    """
    docai_client = DocumentProcessorServiceClient(client_options=_client_options)

    # Specify Output GCS Bucket
    output_config = DocumentOutputConfig(
        gcs_output_config=DocumentOutputConfig.GcsOutputConfig(gcs_uri=gcs_output_uri)
    )

    request = BatchProcessRequest(
        name=processor_name,
        input_documents=input_config,
        document_output_config=output_config,
        skip_human_review=skip_human_review,
    )

    return docai_client.batch_process_documents(request)


def get_operation_metadata(
    operation: Operation, timeout: int = TIMEOUT
) -> BatchProcessMetadata:
    """
    Waits for an operation to complete.
    """
    # The API supports limited concurrent requests.
    logging.info("Waiting for operation %s to complete...", operation.operation.name)
    operation.result(timeout=timeout)

    return BatchProcessMetadata(operation.metadata)


def get_batch_process_output(
    metadata: BatchProcessMetadata,
) -> List[Document]:
    """
    Retrieve Document Objects from GCS after Batch Processing
    """

    if metadata.state != BatchProcessMetadata.State.SUCCEEDED:
        logging.error("Batch Process failed: %s", metadata.state_message)
        return []

    documents: List[Document] = []

    # Should be one process for each source file
    for process in metadata.individual_process_statuses:
        # URI: gs://BUCKET/PREFIX/OPERATION_NUMBER/0
        # Trailing "/" added to prevent "/1/" "/10/" ambiguity
        blobs = get_blobs_from_gcs_uri(f"{process.output_gcs_destination}/")

        # DocAI may output multiple JSON files per source file
        for blob in blobs:
            # Document AI should only output JSON files to GCS
            if blob.content_type != JSON_MIME_TYPE:
                logging.error("Skipping non-json file: %s", blob.name)
                continue
            try:
                logging.info("Fetching from " + blob.name)
                output_document = Document.from_json(
                    blob.download_as_bytes(), ignore_unknown_fields=True
                )

                # Save Source File URI to Document Object
                output_document.uri = process.input_gcs_source
                documents.append(output_document)
            except ParseError:
                logging.error("Failed to parse: %s", blob.name)
                continue

    return documents


def fetch_processor_types(
    project_id: str = DEFAULT_PROJECT_ID, location: str = DEFAULT_LOCATION
) -> Sequence[ProcessorType]:
    """
    Returns a list of processor types enabled for the given project.
    """
    client = BetaDocumentProcessorServiceClient()
    parent = client.common_location_path(project=project_id, location=location)
    response = client.fetch_processor_types(parent=parent)
    return response.processor_types


def create_processor(
    display_name: str,
    processor_type: str,
    project_id: str = DEFAULT_PROJECT_ID,
    location: str = DEFAULT_LOCATION,
) -> Processor:
    """
    Creates a new processor.
    """
    client = BetaDocumentProcessorServiceClient()
    processor = Processor(display_name=display_name, type_=processor_type)
    parent = client.common_location_path(project=project_id, location=location)
    return client.create_processor(parent=parent, processor=processor)
