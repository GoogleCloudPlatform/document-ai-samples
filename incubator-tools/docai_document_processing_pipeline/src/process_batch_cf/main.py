"""
Google Cloud Document AI Batch Processing Module

This module implements a batch processing system for Document AI using Google Cloud services.
It manages concurrent batch processing jobs, handles document queuing, and provides status tracking
through Firestore.

The module supports:
- Concurrent batch processing with configurable limits
- Queue management for pending documents
- Status tracking and updates in Firestore
- Error handling and failed document management
- Automatic triggering of new batch jobs

Environment Variables Required:
    MAX_CONCURRENT_BATCHES: Maximum number of concurrent batch processes allowed (default: 5)
    FIRESTORE_COLLECTION: Name of the Firestore collection for queue management
    PROJECT_ID: Google Cloud Project ID
    LOCATION: Document AI processor location
    PROCESSOR_ID: Document AI processor ID
    PUBSUB_TOPIC_PROCESS: Pub/Sub topic for batch processing
    INPUT_MIME_TYPE: MIME type of input documents
    GCS_OUTPUT_BUCKET: Bucket for processed document outputs
    GCS_OUTPUT_PREFIX: Prefix for output files (optional)
    GCS_FAILED_FILES_BUCKET: Bucket for failed document storage
    GCS_FAILED_FILES_PREFIX: Prefix for failed files
"""

from datetime import datetime
import os
from typing import Any, Callable, Dict, Optional, Union

from cloudevents.http import CloudEvent
import functions_framework
from google.api_core.client_options import ClientOptions
from google.api_core.operation import Operation
from google.cloud import documentai_v1beta3 as documentai
from google.cloud import firestore
from google.cloud import pubsub_v1
from google.cloud import storage
from google.cloud.firestore_v1 import FieldFilter

MAX_CONCURRENT_BATCHES = int(os.environ.get("MAX_CONCURRENT_BATCHES", "5"))
FIRESTORE_COLLECTION = os.environ.get(
    "FIRESTORE_COLLECTION"
)  # Firestore collection name
PROJECT_ID = os.environ.get("PROJECT_ID")
LOCATION = os.environ.get("PROCESSOR_LOCATION")
PROCESSOR_ID = os.environ.get("PROCESSOR_ID")
PUBSUB_TOPIC_PROCESS = os.environ.get("PUBSUB_TOPIC_PROCESS")
INPUT_MIME_TYPE = os.environ.get("INPUT_MIME_TYPE")
GCS_OUTPUT_BUCKET = os.environ.get("GCS_OUTPUT_BUCKET")
GCS_OUTPUT_PREFIX = os.environ.get("GCS_OUTPUT_PREFIX", "")
GCS_FAILED_FILES_BUCKET = os.environ.get("GCS_FAILED_FILES_BUCKET")
GCS_FAILED_FILES_PREFIX = os.environ.get("GCS_FAILED_FILES_PREFIX")

# Initialize Firestore client
db = firestore.Client(PROJECT_ID)


def get_active_batches() -> int:
    """
    Retrieves the count of currently processing batch operations.

    Returns:
        Number of active batch processes in 'processing' state

    Note:
        Queries Firestore for documents with process_mode='batch' and status='processing'
    """

    # Reference to the collection
    collection_ref = db.collection(FIRESTORE_COLLECTION)

    # Query documents where status is 'processing'
    query = collection_ref.where(
        filter=FieldFilter("process_mode", "==", "batch")
    ).where(filter=FieldFilter("status", "==", "processing"))
    docs = query.stream()

    # Count the number of documents in the query result
    active_batches = sum(1 for _ in docs)

    return active_batches


def get_next_item() -> Optional[str]:
    """
    Retrieves the next pending document for batch processing.

    Returns:
        GCS URI of the next document to process, or None if no documents are pending

    Note:
        - Queries for documents with process_mode='batch' and status='pending'
        - Orders by added_time to maintain FIFO processing
        - Returns only one document at a time
    """

    # Reference to the collection
    collection_ref = db.collection(FIRESTORE_COLLECTION)

    # Query documents where status is 'pending', ordered by added_time, limit to 1
    query = (
        collection_ref.where(filter=FieldFilter("process_mode", "==", "batch"))
        .where(filter=FieldFilter("status", "==", "pending"))
        .order_by("added_time")
        .limit(1)
    )
    docs = query.stream()

    # Get the file_path from the first document if it exists
    for doc in docs:
        return doc.to_dict().get("file_path")

    return None


def update_queue_status(
    file_path: str,
    status: str,
    batch_id: Optional[str] = None,
    error: Optional[Exception] = None,
    output_uri: Optional[str] = None,
) -> None:
    """
    Updates the processing status and metadata for a document in Firestore.

    Args:
        file_path: GCS URI of the document
        status: New status ('processing', 'completed', or 'failed')
        batch_id: Batch operation ID for tracking (optional)
        error: Error information if processing failed (optional)
        output_uri: URI of the processed output (optional)

    Note:
        Updates timestamps and additional metadata based on status
    """

    # Reference to the specific document
    collection_ref = db.collection(FIRESTORE_COLLECTION)

    if status == "processing":
        # Prepare the update data
        update_data = {
            "status": status,
            "process_start_time": datetime.utcnow(),  # Firestore will handle Timestamp
            "batch_id": batch_id,
        }

    elif status == "completed":
        update_data = {
            "status": status,
            "process_end_time": datetime.utcnow(),
            "output_uri": output_uri,
        }

    elif status == "failed":
        update_data = {
            "status": status,
            "process_end_time": datetime.utcnow(),
            "error": error,
        }

    try:
        # Query for the document where file_path matches
        query = collection_ref.where(
            filter=FieldFilter("file_path", "==", file_path)
        ).limit(
            1
        )  # Use limit(1) to get a single match

        results = query.stream()  # Execute the query and get the results

        # Iterate through the query results (should be 1 due to limit(1))
        for doc in results:
            # Reference the document to update
            doc_ref = collection_ref.document(doc.id)

            # Update the document
            doc_ref.update(update_data)

    except Exception as e:
        print(f"Error updating queue status to {status} for {file_path}")
        print(e)


def trigger_new_submission() -> None:
    """
    Triggers a new batch submission by publishing a message to Pub/Sub.

    Note:
        Uses PROJECT_ID and PUBSUB_TOPIC_PROCESS environment variables
    """

    topic_path = publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC_PROCESS)
    publisher.publish(topic_path, b"New batch completion, trigger new processing.")


def copy_failed_file_to_folder(
    file_path: str, destination_bucket_name: str, destination_folder: str
) -> None:
    """
    Copies a failed document to a designated failure handling bucket/folder.

    Args:
        file_path: Original GCS URI of the failed file
        destination_bucket_name: Target bucket for failed files
        destination_folder: Target folder path in the destination bucket

    Note:
        Maintains original filename while copying to new location
    """

    # Initialize GCS client
    storage_client = storage.Client()

    # Extract bucket name and blob path from the file path
    source_bucket_name = file_path.split("/")[2]
    source_blob_path = "/".join(file_path.split("/")[3:])
    file_name = os.path.basename(
        source_blob_path
    )  # Get the file name from the blob path

    # Define the destination blob name
    failed_blob_name = f"{destination_folder.rstrip('/')}/{file_name}"

    # Access the source bucket and the original blob
    source_bucket = storage_client.bucket(source_bucket_name)
    source_blob = source_bucket.blob(source_blob_path)

    # Access the destination bucket
    destination_bucket_name = destination_bucket_name.replace("gs://", "").rstrip("/")
    destination_bucket = storage_client.bucket(destination_bucket_name)

    # Copy the failed file to the destination folder
    new_blob = source_bucket.copy_blob(
        source_blob, destination_bucket, failed_blob_name
    )

    print(f"Copied failed file to: gs://{destination_bucket_name}/{failed_blob_name}")


def process_document(file_path: str) -> str:
    """
    Submits a document or folder for batch processing using Document AI.

    Args:
        file_path: GCS URI of the document or folder to process

    Returns:
        Batch operation ID for tracking

    Note:
        - Handles both single documents and folders
        - Sets up callback for batch completion
        - Configures output location and processing parameters
        - Triggers new submission upon completion
    """

    # You must set the `api_endpoint` if you use a location other than "us".
    opts = ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")

    # Call Document AI API to start batch process
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    name = client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)

    if not file_path.endswith("/"):
        # Specify specific GCS URIs to process individual documents
        gcs_document = documentai.GcsDocument(
            gcs_uri=file_path, mime_type=INPUT_MIME_TYPE
        )
        # Load GCS Input URI into a List of document files
        gcs_documents = documentai.GcsDocuments(documents=[gcs_document])
        input_config = documentai.BatchDocumentsInputConfig(gcs_documents=gcs_documents)
    else:
        # Specify a GCS URI Prefix to process an entire directory
        gcs_prefix = documentai.GcsPrefix(gcs_uri_prefix=file_path)
        input_config = documentai.BatchDocumentsInputConfig(gcs_prefix=gcs_prefix)

    # Configuring the batch process request
    output_uri = f"gs://{GCS_OUTPUT_BUCKET.replace('gs://', '').rstrip('/')}/{GCS_OUTPUT_PREFIX.rstrip('/')}/"
    gcs_output_config = documentai.DocumentOutputConfig(
        gcs_output_config=documentai.DocumentOutputConfig.GcsOutputConfig(
            gcs_uri=output_uri
        )
    )

    request = documentai.BatchProcessRequest(
        name=name,
        input_documents=input_config,
        document_output_config=gcs_output_config,
    )

    operation = client.batch_process_documents(request=request)

    batch_id = operation.operation.name

    # Waiting for batch to complete asynchronously
    def my_callback(future, file_path, batch_id, output_uri):
        # Once batch completes, it calls this callback
        if future.exception():
            print(f"Exception occured when processing batch: {batch_id}")
            update_queue_status(
                file_path,
                "failed",
                error=f"Error occured while processing batch operation: {batch_id}",
            )
            copy_failed_file_to_folder(
                file_path, GCS_FAILED_FILES_BUCKET, GCS_FAILED_FILES_PREFIX
            )

        if future.done():
            print(f"Document {file_path} processed successfully")
            update_queue_status(file_path, "completed", output_uri=output_uri)

        trigger_new_submission()

    operation.add_done_callback(
        lambda future: my_callback(
            future, file_path, batch_id, f"{output_uri}{batch_id.split('/')[-1]}/"
        )
    )

    return batch_id  # Return batch process ID


# Triggered from a message on a Cloud Pub/Sub topic.
@functions_framework.cloud_event
def process_batch_documents(event: CloudEvent) -> Union[str, tuple[str, int]]:
    """
    Cloud Function triggered by Pub/Sub to manage batch document processing.

    Args:
        event: Cloud Event trigger from Pub/Sub

    Returns:
        Status message and HTTP status code if slots are available,
        or message indicating maximum concurrent batches reached

    Note:
        - Checks for available processing slots
        - Initiates new batch processes up to MAX_CONCURRENT_BATCHES
        - Continues processing while slots are available and documents are pending
    """

    active_batches = get_active_batches()

    if active_batches >= MAX_CONCURRENT_BATCHES:
        return f"Already running {MAX_CONCURRENT_BATCHES} batches, the file will be processed once a slot is available"

    while active_batches < MAX_CONCURRENT_BATCHES:
        print(active_batches)
        file_path = get_next_item()
        if file_path:
            print("Triggering batch for", file_path)
            batch_id = process_document(file_path)
            update_queue_status(file_path, "processing", batch_id=batch_id)
        else:
            break

        active_batches = get_active_batches()

    return f"Batch triggered, Current active batches = {active_batches}", 200
