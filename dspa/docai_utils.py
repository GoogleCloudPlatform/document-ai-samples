"""
Document AI Utility Functions
"""
from typing import Dict, List
import pikepdf as pike

from google.api_core.client_options import ClientOptions

from google.cloud import documentai_v1 as documentai

from consts import (
    DESTINATION_URI,
    TIMEOUT,
)

from gcs_utils import get_file_from_gcs


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

    return document_entities


def extract_splitter_classifier_entities(
    document: documentai.Document,
) -> Dict[str, List[int]]:
    """
    Extract Classification Values and Page Split Points
    Format: document_classification: [page numbers]
    """
    document_entities: Dict[str, List[int]] = {}

    for entity in document.entities:
        entity_key = entity.type_

        pages_list = []
        for page_ref in entity.page_anchor.page_refs:
            pages_list.append(int(page_ref.page))

        document_entities.update({entity_key: pages_list})

    return document_entities


def split_pdf(gcs_input_file_uri: str, page_mapping: Dict[str, List[int]]) -> None:
    """
    Split PDF based on DocAI Splitter Output
    Save Each Subdocument in GCS Folder by Classification
    """
    input_file_bytes = get_file_from_gcs(gcs_input_file_uri)

    with pike.Pdf.open(input_file_bytes) as original_pdf:

        subdocs = []

        for classification, page_nums in page_mapping.items():
            subdoc = pike.Pdf.new()
            for page_num in page_nums:
                subdoc.pages.append(original_pdf.pages[page_num])
            subdoc.save(
                min_version=original_pdf.pdf_version,
            )
            # Upload to GCS in directory gs://<bucket>/<classification>/filename-pg123.pdf
            # return list of split files
            subdocs.append(subdoc)
    pass


def batch_process_documents(
    processor: Dict,
    batches: List[List[documentai.GcsDocument]],
    gcs_output_uri: str = DESTINATION_URI,
) -> List[str]:
    """
    Constructs requests to process documents using the Document AI
    Batch Method.
    Returns List of Operation IDs
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

    operation_ids: List[str] = []

    for i, batch in enumerate(batches):

        print(f"Processing Document Batch {i}: {len(batch)} documents")

        # Load GCS Input URI into a List of document files
        input_config = documentai.BatchDocumentsInputConfig(
            gcs_documents=documentai.GcsDocuments(documents=batch)
        )
        request = documentai.BatchProcessRequest(
            name=resource_name,
            input_documents=input_config,
            document_output_config=output_config,
        )

        operation = docai_client.batch_process_documents(request)
        operation_ids.append(operation.operation.name)

        # The API supports limited concurrent requests.
        print(f"Waiting for operation {operation.operation.name}")
        operation.result(timeout=TIMEOUT)

    return operation_ids
