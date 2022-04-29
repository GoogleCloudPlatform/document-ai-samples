"""
Sends Documents to Document AI Specialized Processor
Saves Extracted Info to BigQuery
"""

from typing import List, Dict

from consts import (
    GCS_OUTPUT_BUCKET,
    GCS_OUTPUT_PREFIX,
    DESTINATION_URI,
    GCS_SPLIT_PREFIX,
    INVOICE_PARSER_PROCESSOR,
    CUSTOM_SPLITTER_PROCESSOR,
)

from docai_utils import (
    batch_process_documents,
    extract_document_entities,
)

from gcs_utils import (
    create_batches,
    get_document_protos_from_gcs,
    cleanup_gcs,
)

from bq_utils import write_to_bq

from split_pdf import split_pdf_gcs


def bulk_pipeline():
    """
    Bulk Processing of Invoice Documents
    """
    # TODO: Add Classification and mapping step
    batches = create_batches()  # Default INPUT BUCKET, prefix
    operation_ids = batch_process_documents(
        processor=CUSTOM_SPLITTER_PROCESSOR,
        batches=batches,
        gcs_output_uri=DESTINATION_URI,
    )

    # Splitting
    post_processing_splitting(operation_ids)

    # Parsing and Entity Extraction
    batches = create_batches(GCS_OUTPUT_BUCKET, GCS_SPLIT_PREFIX)
    operation_ids = batch_process_documents(
        processor=INVOICE_PARSER_PROCESSOR,
        batches=batches,
        gcs_output_uri=DESTINATION_URI,
    )

    extracted_entities = post_processing_extraction(operation_ids)

    job = write_to_bq(extracted_entities)
    print(job)

    print("Cleaning up Cloud Storage Buckets")
    cleanup_gcs()


def pre_processing():
    """
    Loads documents from GCS and creates batches
    """


def post_processing_splitting(operation_ids: List[str]) -> None:
    """
    Download from GCS and Split PDFs
    """
    for operation_id in operation_ids:

        output_documents = get_document_protos_from_gcs(
            operation_id, GCS_OUTPUT_BUCKET, GCS_OUTPUT_PREFIX
        )
        # TODO: Update once uri field is populated
        for document_proto in output_documents:
            split_pdf_gcs(document_proto, "")


def post_processing_extraction(operation_ids: List[str]) -> List[Dict]:
    """
    Download from GCS and Entity Extraction
    """
    all_document_entities = []

    for operation_id in operation_ids:

        output_documents = get_document_protos_from_gcs(
            operation_id, GCS_OUTPUT_BUCKET, GCS_OUTPUT_PREFIX
        )

        print(f"{len(output_documents)} documents parsed")

        for document_proto in output_documents:
            entities = extract_document_entities(document_proto)
            entities["input_filename"] = document_proto.uri
            all_document_entities.append(entities)

    return all_document_entities
