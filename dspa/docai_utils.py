# type: ignore[1]
"""
Document AI Utility Functions
"""
import logging
from typing import Dict, List

from google.protobuf.json_format import ParseError
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai

from gcs_utils import get_blobs_from_gcs_uri


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


def batch_process_documents(
    processor: Dict,
    document_batch: List[documentai.GcsDocument],
    gcs_output_uri: str,
    skip_human_review: bool = True,
) -> documentai.BatchProcessMetadata:
    """
    Constructs requests to process documents using the Document AI
    Batch Method.
    Returns Batch Process Metadata
    """
    docai_client = documentai.DocumentProcessorServiceClient(
        client_options=ClientOptions(
            api_endpoint=f"{processor['location']}-documentai.googleapis.com"
        )
    )
    resource_name = docai_client.processor_path(
        processor["project_id"], processor["location"], processor["processor_id"]
    )

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
        name=resource_name,
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
        # Trailing / added to prevent "/1/" "/10/" ambiguity
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
