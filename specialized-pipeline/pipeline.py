# type: ignore[1]
"""
Sends Invoices to Document AI API
Saves Extracted Info to BigQuery

"""
import re
from typing import Any, Dict, List, Tuple, Sequence
from collections import deque

from google.api_core.client_options import ClientOptions
from google.api_core.operation import Operation
from google.api_core.exceptions import ResourceExhausted
from google.protobuf.json_format import ParseError

from google.cloud import bigquery
from google.cloud import documentai_v1 as documentai
from google.cloud import storage

# Reading environment variables
PROJECT_ID = "PROJECT_ID"
LOCATION = "us"
PROCESSOR_ID = "PROCESSOR_ID"

BATCH_MAX_FILES = 50
BATCH_MAX_REQUESTS = 5

TIMEOUT = 400

# GCS Variables
gcs_input_bucket = f"{PROJECT_ID}-input-invoices"
gcs_output_bucket = f"{PROJECT_ID}-output-invoices"
gcs_archive_bucket_name = f"{PROJECT_ID}-archived-invoices"

# pylint: disable=invalid-name
gcs_output_prefix = "processed"
destination_uri = f"gs://{gcs_output_bucket}/{gcs_output_prefix}/"

DATSET_NAME = "invoice_parser_results"
ENTITIES_TABLE_NAME = "doc_ai_extracted_entities"

storage_client = storage.Client()
bq_client = bigquery.Client()

ACCEPTED_MIME_TYPES = set(
    ["application/pdf", "image/jpeg", "image/png", "image/tiff", "image/gif"]
)


def write_to_bq(
    dataset_name: str, table_name: str, entities: List[Dict[str, Any]]
) -> Sequence[dict]:
    """
    Write Data to BigQuery
    """
    dataset_ref = bq_client.dataset(dataset_name, project=PROJECT_ID)
    table = bq_client.get_table(dataset_ref.table(table_name))

    job = bq_client.insert_rows(
        table, entities, skip_invalid_rows=True, ignore_unknown_values=True
    )

    return job


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


def create_batches(
    input_bucket: str, input_prefix: str, batch_size: int = BATCH_MAX_FILES
) -> List[List[documentai.GcsDocument]]:
    """
    Create batches of documents to process
    """
    if batch_size > BATCH_MAX_FILES:
        raise ValueError(
            f"Batch size must be less than {BATCH_MAX_FILES}. "
            f"You provided {batch_size}"
        )

    blob_list = storage_client.list_blobs(input_bucket, prefix=input_prefix)

    batches: List[List[documentai.GcsDocument]] = []
    batch: List[documentai.GcsDocument] = []

    for blob in blob_list:

        if blob.content_type not in ACCEPTED_MIME_TYPES:
            print(f"Invalid Mime Type {blob.content_type} - Skipping file {blob.name}")
            continue

        if len(batch) == batch_size:
            batches.append(batch)
            batch = []

        batch.append(
            documentai.GcsDocument(
                gcs_uri=f"gs://{input_bucket}/{blob.name}",
                mime_type=blob.content_type,
            )
        )

    batches.append(batch)

    return batches


def wait_for_operation(operation: Operation) -> None:
    """
    Wait for an operation to complete
    """
    print(f"Waiting for operation {operation.operation.name}")
    operation.result(timeout=TIMEOUT)


def _batch_process_documents(
    gcs_output_uri: str,
    input_bucket: str,
    input_prefix: str,
    batch_size: int = BATCH_MAX_FILES,
) -> List[str]:
    """
    Constructs a request to process a document using the Document AI
    Batch Method.
    """
    docai_client = documentai.DocumentProcessorServiceClient(
        client_options=ClientOptions(
            api_endpoint=f"{LOCATION}-documentai.googleapis.com"
        )
    )
    resource_name = docai_client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)

    output_config = documentai.DocumentOutputConfig(
        gcs_output_config=documentai.DocumentOutputConfig.GcsOutputConfig(
            gcs_uri=gcs_output_uri
        )
    )

    batches = create_batches(input_bucket, input_prefix, batch_size)
    operation_queue: deque[Operation] = deque()
    operation_ids: List[str] = []

    for i, batch in enumerate(batches):
        # If the operation queue is close to quota, wait for an operation to complete
        if i >= BATCH_MAX_REQUESTS - 1:
            print("Close to Quota")
            wait_for_operation(operation_queue.popleft())

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
        try:
            operation = docai_client.batch_process_documents(request)
        except ResourceExhausted:
            print("Quota Exhausted")
            wait_for_operation(operation_queue.popleft())
            operation = docai_client.batch_process_documents(request)
        finally:
            operation_queue.append(operation)
            operation_ids.append(operation.operation.name)

    for operation in operation_queue:
        wait_for_operation(operation)

    return operation_ids


def get_document_protos_from_gcs(
    output_bucket: str, output_directory: str
) -> Tuple[List[documentai.Document], List[str]]:
    """
    Download document proto output from GCS. (Directory)
    """

    # List of all of the files in the directory
    # `gs://gcs_output_uri/operation_id`
    blob_list = storage_client.list_blobs(output_bucket, prefix=output_directory)

    document_protos = []
    parsing_errors = []

    for blob in blob_list:
        # Document AI should only output JSON files to GCS
        if ".json" in blob.name:
            try:
                document_proto = documentai.types.Document.from_json(
                    blob.download_as_bytes()
                )
            except ParseError:
                print(f"Failed to parse {blob.name}")
                parsing_errors.append(blob.name)
                continue

            print("Fetching from " + blob.name)
            document_protos.append(document_proto)
        else:
            print(f"Skipping non-supported file type {blob.name}")

    return document_protos, parsing_errors


# pylint: disable=too-many-arguments
def cleanup_gcs(
    input_bucket: str,
    input_prefix: str,
    output_bucket: str,
    output_directory: str,
    archive_bucket: str,
    parsing_errors: List[str],
):
    """
    Deleting the intermediate files created by the Doc AI Parser
    Moving Input Files to Archive
    """

    delete_queue = []

    # Intermediate document.json files
    intermediate_files = storage_client.list_blobs(
        output_bucket, prefix=output_directory
    )

    for blob in intermediate_files:
        # For now, don't remove json files that couldn't be parsed.
        if blob.name not in parsing_errors:
            delete_queue.append(blob)

    # Copy input files to archive bucket
    source_bucket = storage_client.bucket(input_bucket)
    destination_bucket = storage_client.bucket(archive_bucket)

    source_blobs = storage_client.list_blobs(input_bucket, prefix=input_prefix)

    for source_blob in source_blobs:
        print(
            f"Moving {source_bucket}/{source_blob.name} to {archive_bucket}/{source_blob.name}"
        )
        source_bucket.copy_blob(source_blob, destination_bucket, source_blob.name)
        delete_queue.append(source_blob)

    for blob in delete_queue:
        print(f"Deleting {blob.name}")
        blob.delete()


def bulk_pipeline():
    """
    Bulk Processing of Invoice Documents
    """
    gcs_input_prefix = ""

    operation_ids = _batch_process_documents(
        gcs_output_uri=destination_uri,
        input_bucket=gcs_input_bucket,
        input_prefix=gcs_input_prefix,
    )

    all_document_entities = []
    all_parsing_errors = []

    for operation_id in operation_ids:
        # Output files will be in a new subdirectory with Operation Number as the name
        operation_number = re.search(
            r"operations\/(\d+)", operation_id, re.IGNORECASE
        ).group(1)

        output_directory = f"{gcs_output_prefix}/{operation_number}"

        output_document_protos, parsing_errors = get_document_protos_from_gcs(
            gcs_output_bucket, output_directory
        )
        all_parsing_errors.append(parsing_errors)

        print(f"{len(output_document_protos)} documents parsed")
        print(f"{len(parsing_errors)} documents failed to parse")

        for document_proto in output_document_protos:
            entities = extract_document_entities(document_proto)
            entities["input_filename"] = document_proto.uri
            all_document_entities.append(entities)

    job = write_to_bq(DATSET_NAME, ENTITIES_TABLE_NAME, all_document_entities)
    print(job)

    print("Cleaning up Cloud Storage Buckets")
    cleanup_gcs(
        gcs_input_bucket,
        gcs_input_prefix,
        gcs_output_bucket,
        gcs_output_prefix,
        gcs_archive_bucket_name,
        parsing_errors,
    )


bulk_pipeline()
