# mypy: disable-error-code="1"
"""
Sends Invoices to Document AI API
Saves Extracted Info to BigQuery
Sends addresses to Geocoding PubSub Topic.
"""
import json
import os
import re
from typing import Any, Dict, List

from google.api_core.client_options import ClientOptions
from google.api_core.operation import Operation
from google.cloud import bigquery
from google.cloud import documentai_v1 as documentai
from google.cloud import pubsub_v1
from google.cloud import storage

# Reading environment variables
gcs_output_uri_prefix = os.environ.get("GCS_OUTPUT_URI_PREFIX")
PROJECT_ID = os.environ.get("GCP_PROJECT")
LOCATION = os.environ.get("PARSER_LOCATION")
PROCESSOR_ID = os.environ.get("PROCESSOR_ID")
geocode_request_topicname = os.environ.get("GEOCODE_REQUEST_TOPICNAME")
timeout = int(os.environ.get("TIMEOUT"))

# An array of Future objects
# Every call to publish() returns an instance of Future
geocode_futures = []

# Setting variables
address_fields = [
    "receiver_address",
    "remit_to_address",
    "ship_from_address",
    "ship_to_address",
    "supplier_address",
]

# GCS Variables
gcs_output_bucket = f"{PROJECT_ID}-output-invoices"
gcs_archive_bucket_name = f"{PROJECT_ID}-archived-invoices"
destination_uri = f"gs://{gcs_output_bucket}/{gcs_output_uri_prefix}/"

DATSET_NAME = "invoice_parser_results"
ENTITIES_TABLE_NAME = "doc_ai_extracted_entities"

client_options = ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")

docai_client = documentai.DocumentProcessorServiceClient(client_options=client_options)

storage_client = storage.Client()
bq_client = bigquery.Client()
pub_client = pubsub_v1.PublisherClient()

ACCEPTED_MIME_TYPES = set(
    ["application/pdf", "image/jpeg", "image/png", "image/tiff", "image/gif"]
)


def write_to_bq(dataset_name, table_name, entities_extracted_dict):
    """
    Write Data to BigQuery
    """
    dataset_ref = bq_client.dataset(dataset_name)
    table_ref = dataset_ref.table(table_name)
    row_to_insert = []
    row_to_insert.append(entities_extracted_dict)

    json_data = json.dumps(row_to_insert, sort_keys=False)
    # Convert to a JSON Object
    json_object = json.loads(json_data)

    schema_update_options = [
        bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION,
        bigquery.SchemaUpdateOption.ALLOW_FIELD_RELAXATION,
    ]
    source_format = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON

    job_config = bigquery.LoadJobConfig(
        schema_update_options=schema_update_options,
        source_format=source_format,
    )

    job = bq_client.load_table_from_json(json_object, table_ref, job_config=job_config)
    print(job.result())  # Waits for table load to complete.


def extract_document_entities(document: documentai.Document) -> dict:
    """
    Get all entities from a document and output as a dictionary
    Flattens nested entities/properties
    Format: entity.type_: entity.mention_text OR entity.normalized_value.text
    """
    document_entities: Dict[str, Any] = {}

    def extract_document_entity(entity: documentai.Document.Entity):
        """
        Extract Single Entity and Add to Entity Dictionary
        """
        entity_key = entity.type_.replace("/", "_")
        normalized_value = getattr(entity, "normalized_value", None)

        new_entity_value = (
            normalized_value.text if normalized_value else entity.mention_text
        )

        existing_entity = document_entities.get(entity_key)

        # For entities that can have multiple (e.g. line_item)
        if existing_entity:
            # Change Entity Type to a List
            if not isinstance(existing_entity, list):
                existing_entity = list([existing_entity])

            existing_entity.append(new_entity_value)
            document_entities[entity_key] = existing_entity
        else:
            document_entities.update({entity_key: new_entity_value})

    for entity in document.entities:
        # Fields detected. For a full list of fields for each processor see
        # the processor documentation:
        # https://cloud.google.com/document-ai/docs/processors-list
        extract_document_entity(entity)

        # Properties are Sub-Entities
        for prop in entity.properties:
            extract_document_entity(prop)

    return document_entities


def _batch_process_documents(
    project_id: str,
    location: str,
    processor_id: str,
    gcs_input_uri: str,
    gcs_output_uri: str,
) -> Operation:
    """
    Constructs a request to process a document using the Document AI
    Batch Method.
    """

    # The full resource name of the processor, e.g.:
    # projects/project-id/locations/location/processor/processor-id
    # You must create new processors in the Cloud Console first
    resource_name = docai_client.processor_path(project_id, location, processor_id)

    # Load GCS Input URI Prefix into Input Config Object
    input_config = documentai.BatchDocumentsInputConfig(
        gcs_prefix=documentai.GcsPrefix(gcs_uri_prefix=gcs_input_uri)
    )

    # Cloud Storage URI for Output directory
    gcs_output_config = documentai.DocumentOutputConfig.GcsOutputConfig(
        gcs_uri=gcs_output_uri
    )

    # Load GCS Output URI into Output Config Object
    output_config = documentai.DocumentOutputConfig(gcs_output_config=gcs_output_config)

    # Configure Process Request
    request = documentai.BatchProcessRequest(
        name=resource_name,
        input_documents=input_config,
        document_output_config=output_config,
    )

    # Future for long-running operations returned from Google Cloud APIs.
    operation = docai_client.batch_process_documents(request)

    return operation


def get_document_protos_from_gcs(
    output_bucket: str, output_directory: str
) -> List[documentai.Document]:
    """
    Download document proto output from GCS. (Directory)
    """

    # List of all of the files in the directory
    # `gs://gcs_output_uri/operation_id`
    blob_list = list(storage_client.list_blobs(output_bucket, prefix=output_directory))

    document_protos = []

    for blob in blob_list:
        # Document AI should only output JSON files to GCS
        if ".json" in blob.name:
            print("Fetching from " + blob.name)
            document_proto = documentai.types.Document.from_json(
                blob.download_as_bytes()
            )
            document_protos.append(document_proto)
        else:
            print(f"Skipping non-supported file type {blob.name}")

    return document_protos


def cleanup_gcs(
    input_bucket: str,
    input_filename: str,
    output_bucket: str,
    output_directory: str,
    archive_bucket: str,
):
    """
    Deleting the intermediate files created by the Doc AI Parser
    Moving Input Files to Archive
    """

    # Intermediate document.json files
    blob_list = list(storage_client.list_blobs(output_bucket, prefix=output_directory))

    for blob in blob_list:
        blob.delete()

    # Copy input file to archive bucket
    source_bucket = storage_client.bucket(input_bucket)
    source_blob = source_bucket.blob(input_filename)
    destination_bucket = storage_client.bucket(archive_bucket)

    source_bucket.copy_blob(source_blob, destination_bucket, input_filename)

    # delete from the input folder
    source_blob.delete()


def process_address(address_type: str, address_value: str, input_filename: str):
    """
    Creating and publishing a message via Pub Sub
    """
    message = {
        "entity_type": address_type,
        "entity_text": address_value,
        "input_file_name": input_filename,
    }
    message_data = json.dumps(message).encode("utf-8")

    geocode_topic_path = pub_client.topic_path(PROJECT_ID, geocode_request_topicname)
    geocode_future = pub_client.publish(geocode_topic_path, data=message_data)
    geocode_futures.append(geocode_future)


# pylint: disable=unused-argument
def process_invoice(event, context):
    """
    Extract Invoice Entities and Save to BQ
    """
    input_bucket = event.get("bucket")
    input_filename = event.get("name")
    mime_type = event.get("contentType")

    if not input_bucket or not input_filename:
        print("No bucket or filename provided")
        return

    if mime_type not in ACCEPTED_MIME_TYPES:
        print("Cannot parse the file type: " + mime_type)
        return

    print("Mime Type: " + mime_type)

    gcs_input_uri = f"gs://{input_bucket}/{input_filename}"

    print("Input File: " + gcs_input_uri)

    operation = _batch_process_documents(
        PROJECT_ID, LOCATION, PROCESSOR_ID, gcs_input_uri, destination_uri
    )

    print("Document Processing Operation: " + operation.operation.name)

    # Wait for the operation to finish
    operation.result(timeout=timeout)

    # Output files will be in a new subdirectory with Operation ID as the name
    operation_id = re.search(
        r"operations\/(\d+)", operation.operation.name, re.IGNORECASE
    ).group(1)

    output_directory = f"{gcs_output_uri_prefix}/{operation_id}"
    print(f"Output Path: gs://{gcs_output_bucket}/{output_directory}")

    print("Output files:")

    output_document_protos = get_document_protos_from_gcs(
        gcs_output_bucket, output_directory
    )

    # Reading all entities into a dictionary to write into a BQ table

    for document_proto in output_document_protos:
        entities = extract_document_entities(document_proto)
        entities["input_file_name"] = input_filename

        print("Entities:", entities)
        print("Writing DocAI Entities to BQ")

        # Add Entities to DocAI Extracted Entities Table
        write_to_bq(DATSET_NAME, ENTITIES_TABLE_NAME, entities)

        # Send Address Data to PubSub
        for address_field in address_fields:
            if address_field in entities:
                process_address(address_field, entities[address_field], input_filename)

    cleanup_gcs(
        input_bucket,
        input_filename,
        gcs_output_bucket,
        output_directory,
        gcs_archive_bucket_name,
    )
    return
