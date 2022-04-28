# type: ignore[1]
"""
Sends Documents to Document AI Specialized Processor
Saves Extracted Info to BigQuery
"""

import re
from typing import List, Dict

from consts import (
    GCS_OUTPUT_BUCKET,
    GCS_OUTPUT_PREFIX,
    DESTINATION_URI,
    INVOICE_PARSER_PROCESSOR,
    CUSTOM_SPLITTER_PROCESSOR,
)

from docai_utils import batch_process_documents, extract_document_entities
from gcs_utils import create_batches, get_document_protos_from_gcs, cleanup_gcs
from bq_utils import write_to_bq


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

    # Parsing and Entity Extraction
    batches = create_batches()
    operation_ids = batch_process_documents(
        processor=INVOICE_PARSER_PROCESSOR,
        batches=batches,
        gcs_output_uri=DESTINATION_URI,
    )

    extracted_entities = post_processing(operation_ids)

    job = write_to_bq(extracted_entities)
    print(job)

    print("Cleaning up Cloud Storage Buckets")
    cleanup_gcs()


def pre_processing():
    """
    Loads documents from GCS and creates batches
    """
    pass


def post_processing(operation_ids: List[str]) -> List[Dict]:
    """
    Download from GCS and Entity Extraction
    """
    all_document_entities = []

    for operation_id in operation_ids:
        # Output files will be in a new subdirectory with Operation Number as the name
        operation_number = re.search(
            r"operations\/(\d+)", operation_id, re.IGNORECASE
        ).group(1)

        output_directory = f"{GCS_OUTPUT_PREFIX}/{operation_number}"

        output_document_protos = get_document_protos_from_gcs(
            GCS_OUTPUT_BUCKET, output_directory
        )

        print(f"{len(output_document_protos)} documents parsed")

        for document_proto in output_document_protos:
            entities = extract_document_entities(document_proto)
            entities["input_filename"] = document_proto.uri
            all_document_entities.append(entities)

    return all_document_entities


bulk_pipeline()
