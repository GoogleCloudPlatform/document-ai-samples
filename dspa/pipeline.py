"""
Sends Documents to Document AI Specialized Processor
Saves Extracted Info to BigQuery
"""

from typing import List, Dict, Set

from consts import (
    GCS_INPUT_BUCKET,
    GCS_INPUT_PREFIX,
    GCS_ARCHIVE_BUCKET,
    DESTINATION_URI,
    GCS_SPLIT_BUCKET,
    GCS_SPLIT_PREFIX,
    CUSTOM_SPLITTER_PROCESSOR,
    DOCUMENT_PROCESSOR_MAP,
)

from docai_utils import (
    batch_process_documents,
    extract_document_entities,
    get_batch_process_output,
)

from gcs_utils import (
    create_batches,
    cleanup_gcs,
)

from bq_utils import write_to_bq

from split_pdf import split_pdf_gcs


def bulk_pipeline():
    """
    Bulk Processing of Invoice Documents
    Runs Splitter/Classifier
    Uses Output of Splitter to Split PDF File by Classification
    Sends Split PDFs to mapped Document AI Specialized Processor
    """

    # Splitter/Classifier Batch Processing
    batch_process_results = batch_process_bulk(
        gcs_input_bucket=GCS_INPUT_BUCKET,
        gcs_input_prefix=GCS_INPUT_PREFIX,
        processor=CUSTOM_SPLITTER_PROCESSOR,
        gcs_output_uri=DESTINATION_URI,
    )

    # Split PDFs By Classification and Output in GCS
    classifications = post_processing_splitting(
        batch_process_results, GCS_SPLIT_BUCKET, GCS_SPLIT_PREFIX
    )

    # For each Classification, create Batches and send to Document AI Specialized Parser
    for classification in classifications:
        specialized_parser = DOCUMENT_PROCESSOR_MAP[classification]
        classification_directory = f"{GCS_SPLIT_PREFIX}/{classification}"

        print(f"Processing {classification_directory} with {specialized_parser}")

        batch_process_results = batch_process_bulk(
            gcs_input_bucket=GCS_SPLIT_BUCKET,
            gcs_input_prefix=classification_directory,
            processor=specialized_parser,
            gcs_output_uri=DESTINATION_URI,
        )

        # Parsing and Entity Extraction
        all_document_entities = post_processing_extraction(batch_process_results)

        # Write to BigQuery
        job = write_to_bq(all_document_entities)
        print(job)

    # print("Cleaning up Cloud Storage Buckets")
    # cleanup_gcs(
    #     input_bucket=GCS_INPUT_BUCKET,
    #     input_prefix=GCS_INPUT_PREFIX,
    #     archive_bucket=GCS_ARCHIVE_BUCKET,
    # )


def batch_process_bulk(
    gcs_input_bucket: str, gcs_input_prefix: str, processor: Dict, gcs_output_uri: str
) -> List:
    """
    Load documents from GCS
    Create Batches
    Call BatchProcessMethod
    Return BatchProcessMetadata for each batch
    """
    batches = create_batches(gcs_input_bucket, gcs_input_prefix)
    batch_process_results = []

    for i, batch in enumerate(batches):

        if len(batch) <= 0:
            continue

        # TODO: Remove when testing is complete
        if i > 1:
            break

        print(f"Processing Document Batch {i}: {len(batch)} documents")

        batch_process_metadata = batch_process_documents(
            processor=processor,
            document_batch=batch,
            gcs_output_uri=gcs_output_uri,
        )

        print(batch_process_metadata.state_message)

        batch_process_results.append(batch_process_metadata)

    return batch_process_results


def post_processing_splitting(
    batch_process_results: List,
    gcs_split_bucket: str,
    gcs_split_prefix: str,
) -> Set[str]:
    """
    Download from GCS and Split PDFs
    Return Set of Classifications
    """

    classifications: Set[str] = set()
    for result in batch_process_results:
        output_documents = get_batch_process_output(result)
        for document in output_documents:
            classifications = classifications.union(
                split_pdf_gcs(document, gcs_split_bucket, gcs_split_prefix)
            )
    return classifications


def post_processing_extraction(
    batch_process_results: List,
) -> List[Dict]:
    """
    Download from GCS and Entity Extraction
    """
    all_document_entities: List[Dict] = []

    for result in batch_process_results:
        output_documents = get_batch_process_output(result)

        print(f"{len(output_documents)} documents parsed")

        for document in output_documents:
            entities = extract_document_entities(document)
            all_document_entities.append(entities)

    return all_document_entities


bulk_pipeline()
