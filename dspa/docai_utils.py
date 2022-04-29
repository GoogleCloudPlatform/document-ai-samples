"""
Document AI Utility Functions
"""
from typing import Dict, List

from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai

from consts import DESTINATION_URI, TIMEOUT


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


def batch_process_documents(
    processor: Dict,
    batches: List[List[documentai.GcsDocument]],
    gcs_output_uri: str = DESTINATION_URI,
) -> List[str]:
    """
    Constructs requests to process documents using the Document AI
    Batch Method.
    Returns List of Operation IDs
        Format: projects/PROJECT_NUMBER/locations/LOCATION/operations/OPERATION_NUMBER
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
