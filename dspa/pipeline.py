# type: ignore[1]
"""
Sends Documents to Document AI Specialized Processor
Saves Extracted Info to BigQuery
"""

import re
from typing import List

from consts import (
    gcs_input_bucket,
    gcs_input_prefix,
    gcs_output_bucket,
    gcs_archive_bucket_name,
    gcs_output_prefix,
    destination_uri,
)

from docai_utils import (
    _batch_process_documents,
    get_document_protos_from_gcs,
    extract_document_entities,
    cleanup_gcs,
)

from bq_utils import write_to_bq


def bulk_pipeline():
    """
    Bulk Processing of Invoice Documents
    """

    operation_ids = _batch_process_documents(
        gcs_output_uri=destination_uri,
        input_bucket=gcs_input_bucket,
        input_prefix=gcs_input_prefix,
    )

    return operation_ids


def post_processing(operation_ids: List[str]):
    """
    Entity Extraction and output to BigQuery
    """
    all_document_entities = []

    for operation_id in operation_ids:
        # Output files will be in a new subdirectory with Operation Number as the name
        operation_number = re.search(
            r"operations\/(\d+)", operation_id, re.IGNORECASE
        ).group(1)

        output_directory = f"{gcs_output_prefix}/{operation_number}"

        output_document_protos = get_document_protos_from_gcs(
            gcs_output_bucket, output_directory
        )

        print(f"{len(output_document_protos)} documents parsed")

        for document_proto in output_document_protos:
            entities = extract_document_entities(document_proto)
            entities["input_filename"] = document_proto.uri
            all_document_entities.append(entities)

    job = write_to_bq(all_document_entities)
    print(job)

    print("Cleaning up Cloud Storage Buckets")
    cleanup_gcs(
        gcs_input_bucket,
        gcs_input_prefix,
        gcs_output_bucket,
        gcs_output_prefix,
        gcs_archive_bucket_name,
    )


completed_operation_ids = bulk_pipeline()

post_processing(completed_operation_ids)
