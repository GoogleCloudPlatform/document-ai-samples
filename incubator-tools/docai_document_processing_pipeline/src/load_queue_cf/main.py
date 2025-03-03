# pylint: disable=C0301
# pylint: disable=W0212
# pylint: disable=E0606
# pylint: disable=W0718
# pylint: disable=R1721
# pylint: disable=R1710
"""
Google Cloud Document AI Processing Pipeline

This module implements a document processing pipeline using Google Cloud services including
Document AI, Cloud Storage, Firestore, and Cloud Pub/Sub. It handles both synchronous and batch
processing of documents based on their size and complexity.

The pipeline supports:
- Loading documents from GCS buckets
- Tracking document processing status in Firestore
- Synchronous processing for small documents
- Batch processing for larger documents
- Error handling and failed document management

Environment Variables Required:
    PROJECT_ID: Google Cloud Project ID
    FIRESTORE_COLLECTION: Name of the Firestore collection for queue management
    PUBSUB_TOPIC_PROCESS: Pub/Sub topic for triggering batch processing
    LOCATION: Document AI processor location
    PROCESSOR_ID: Document AI processor ID
    INPUT_MIME_TYPE: MIME type of input documents
    GCS_OUTPUT_BUCKET: Bucket for processed document outputs
    GCS_OUTPUT_PREFIX: Prefix for output files (optional)
    GCS_FAILED_FILES_BUCKET: Bucket for failed document storage
    GCS_FAILED_FILES_PREFIX: Prefix for failed files
"""

from datetime import datetime
import json
import os
import tempfile
from typing import List, Optional

from flask import Request
import functions_framework
from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import GoogleAPIError
from google.api_core.exceptions import ResourceExhausted
from google.cloud import documentai_v1beta3 as documentai
from google.cloud import firestore
from google.cloud import pubsub_v1
from google.cloud import storage
from google.cloud.firestore_v1 import FieldFilter
from google.protobuf.json_format import MessageToDict
import PyPDF2

# Variables
PROJECT_ID = os.environ.get("PROJECT_ID")
FIRESTORE_COLLECTION = os.environ.get(
    "FIRESTORE_COLLECTION"
)  # Firestore collection name
PUBSUB_TOPIC_PROCESS = os.environ.get("PUBSUB_TOPIC_PROCESS")
LOCATION = os.environ.get("PROCESSOR_LOCATION")
PROCESSOR_ID = os.environ.get("PROCESSOR_ID")
INPUT_MIME_TYPE = os.environ.get("INPUT_MIME_TYPE")
GCS_OUTPUT_BUCKET = os.environ.get("GCS_OUTPUT_BUCKET", "")
GCS_OUTPUT_PREFIX = os.environ.get("GCS_OUTPUT_PREFIX", "")
GCS_FAILED_FILES_BUCKET = os.environ.get("GCS_FAILED_FILES_BUCKET", "")
GCS_FAILED_FILES_PREFIX = os.environ.get("GCS_FAILED_FILES_PREFIX", "")

# Initialize Firestore client
db = firestore.Client(PROJECT_ID)

# Initialize Pub/Sub client
publisher = pubsub_v1.PublisherClient()


def list_files_in_gcs_folder(bucket_name: str, folder_name: str) -> List[str]:
    """
    Lists all files in a specified Google Cloud Storage folder.

    Args:
        bucket_name: Name of the GCS bucket
        folder_name: Path to the folder within the bucket

    Returns:
        List of complete GCS URIs (gs://) for all files in the folder

    Note:
        Excludes folder objects (objects ending with '/')
    """

    # Initialize a client
    storage_client = storage.Client()

    # Get the bucket
    bucket = storage_client.bucket(bucket_name)

    # Define the prefix to filter files in the folder
    blobs = bucket.list_blobs(prefix=folder_name)

    # List all files in the folder
    file_list = []
    for blob in blobs:
        # Exclude subfolders or the folder itself (if it ends with /)
        if not blob.name.endswith("/"):
            file_list.append("gs://" + bucket_name + "/" + blob.name)

    return file_list


def download_file_from_gcs(gcs_uri: str, local_temp_path: str) -> None:
    """
    Downloads a file from Google Cloud Storage to a local temporary location.

    Args:
        gcs_uri: Complete GCS URI (gs://) of the file to download
        local_temp_path: Local file path where the file should be saved

    Note:
        Handles the parsing of GCS URI and blob retrieval automatically
    """

    # Initialize a client
    storage_client = storage.Client()

    bucket_name, blob_name = gcs_uri.replace("gs://", "").split("/", 1)
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.download_to_filename(local_temp_path)


def get_pdf_page_count(local_pdf_path: str) -> Optional[int]:
    """
    Determines the number of pages in a PDF document.

    Args:
        local_pdf_path: Path to the local PDF file

    Returns:
        Number of pages in the PDF, or None if there's an error

    Note:
        Uses PyPDF2 for PDF parsing
    """

    try:
        with open(local_pdf_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            return len(reader.pages)
    except Exception as e:
        print(f"Error reading PDF file: {e}")
        return None


def get_sync_batch(gcs_input_uri: str) -> Optional[str]:
    """
    Determines whether a document should be processed synchronously or in batch mode
    based on page count.

    Args:
        gcs_input_uri: GCS URI of the input document

    Returns:
        'sync' for documents <= 15 pages, 'batch' for larger documents,
        None if page count cannot be determined

    Note:
        Downloads file temporarily to check page count
    """

    # Download the file from GCS to a temporary location
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
        local_pdf_path = temp_file.name
        download_file_from_gcs(gcs_input_uri, local_pdf_path)

    # Check the page count using PyPDF2
    page_count = get_pdf_page_count(local_pdf_path)

    if page_count is None:
        print("Unable to get page count. Skipping processing.")
        return None

    # Process synchronously if less than 15 pages
    if page_count <= 15:
        return "sync"
    return "batch"


def populate_queue(file_paths: List[str]) -> None:
    """
    Initializes Firestore documents for tracking document processing status.

    Args:
        file_paths: List of GCS URIs for documents to be processed

    Note:
        - Creates documents with initial status 'pending'
        - Includes timestamps and processing mode determination
        - Handles errors for individual document insertion
    """

    # Reference to the collection
    collection_ref = db.collection(FIRESTORE_COLLECTION)

    for path in file_paths:
        # Prepare the document data
        doc_data = {
            "file_path": path,
            "status": "pending",
            "process_mode": get_sync_batch(path),
            "added_time": datetime.utcnow(),  # Firestore will automatically handle timestamp conversion
            "process_start_time": None,  # Initialize with None or a default value
            "process_end_time": None,
        }

        try:
            # Add a new document with the data
            collection_ref.add(doc_data)
        except Exception as e:
            print(f"Couldn't insert {path} into Firestore collection", e)
            continue

    print(
        f"Successfully inserted {len(file_paths)} documents into Firestore collection."
    )


def trigger_batch_processing() -> None:
    """
    Publishes a message to Pub/Sub to initiate batch document processing.

    Note:
        Uses PROJECT_ID and PUBSUB_TOPIC_PROCESS environment variables
        Returns the message ID from Pub/Sub publish operation
    """

    topic_path = publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC_PROCESS)

    message_data = b"Start batch processing"  # Message body
    future = publisher.publish(topic_path, message_data)
    print(f"Message published to {PUBSUB_TOPIC_PROCESS}: {future.result()}")


def save_json_to_gcs(
    data: str, destination_bucket: str, filename: str, prefix_folder: str
) -> str:
    """
    Saves JSON data to a specified location in Google Cloud Storage.

    Args:
        data: JSON data to save
        destination_bucket: Target GCS bucket name
        filename: Desired filename for the JSON file
        prefix_folder: Folder prefix for the file

    Returns:
        Complete GCS URI of the saved file

    Note:
        Automatically handles bucket name formatting and folder structure
    """

    # Initialize Google Cloud Storage client
    storage_client = storage.Client()

    # Remove 'gs://' if present from the bucket name
    bucket_name = destination_bucket.replace("gs://", "")

    # Get the bucket object
    bucket = storage_client.get_bucket(bucket_name)

    # If a prefix folder is provided, add it to the filename
    if prefix_folder:
        # Ensure prefix ends with a slash to format correctly as a folder
        prefix_folder = prefix_folder.rstrip("/") + "/"
        filename = prefix_folder + filename

    # Create a blob with the updated filename
    blob = bucket.blob(filename)

    # Upload the JSON data as a string to the blob
    blob.upload_from_string(data, content_type="application/json")

    # Generate and return the output URI
    output_uri = f"gs://{bucket.name}/{filename}"
    return output_uri


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
    source_bucket.copy_blob(source_blob, destination_bucket, failed_blob_name)

    print(f"Copied failed file to: gs://{destination_bucket_name}/{failed_blob_name}")


def process_document_sync(gcs_input_uri: str) -> bool:
    """
    Processes a document synchronously using Document AI.

    Args:
        gcs_input_uri: GCS URI of the document to process

    Returns:
        True if processing successful, False if failed

    Note:
        - Updates document status in Firestore throughout processing
        - Handles quota exhaustion by switching to batch mode
        - Moves failed documents to failure bucket
        - Saves processed output as JSON to designated bucket
    """

    try:
        # Updating the queue status to log process_start_time
        update_queue_status(gcs_input_uri, "processing")

        # You must set the `api_endpoint` if you use a location other than "us".
        opts = ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")

        client = documentai.DocumentProcessorServiceClient(client_options=opts)

        # Full resource name for the processor
        name = client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)

        # Specify the input document's GCS URI
        gcs_document = documentai.types.GcsDocument(
            gcs_uri=gcs_input_uri, mime_type=INPUT_MIME_TYPE
        )

        # Create a document processing request
        request = documentai.types.ProcessRequest(name=name, gcs_document=gcs_document)

        response = client.process_document(request=request)

        # Convert response to JSON string
        document_dict = MessageToDict(response.document._pb)
        response_json = json.dumps(document_dict)

        # Extracting file name from GCS uri
        file_name = ".".join(gcs_input_uri.split("/")[-1].split(".")[:-1])

        # Save output as JSON to GCS
        output_uri = save_json_to_gcs(
            response_json,
            GCS_OUTPUT_BUCKET,
            f"{file_name}.json",
            prefix_folder=GCS_OUTPUT_PREFIX,
        )

        # Updating queue status as completed
        update_queue_status(gcs_input_uri, "completed", output_uri=output_uri)

        print(f"Processed document synchronously. Output saved to {output_uri}")

        return True  # Successfully processed the document synchronously

    except ResourceExhausted:
        print("Quota limit hit for synchronous processing")
        # Moving to batch mode if Quota limit hit
        update_sync_to_batch(gcs_input_uri)
        trigger_batch_processing()
        return True

    except GoogleAPIError as e:
        print(f"Error during synchronous processing: {e}")
        # Other errors, mark as error
        update_queue_status(gcs_input_uri, "failed", error=e)
        copy_failed_file_to_folder(
            gcs_input_uri, GCS_FAILED_FILES_BUCKET, GCS_FAILED_FILES_PREFIX
        )
        return False


def update_sync_to_batch(file_path: str) -> None:
    """
    Updates a document's processing mode from synchronous to batch in Firestore.

    Args:
        file_path: GCS URI of the document to update

    Note:
        Resets process_start_time when switching to batch mode
    """

    # Reference to the specific document
    collection_ref = db.collection(FIRESTORE_COLLECTION)

    # Prepare the update data
    update_data = {
        "process_mode": "batch",
        "process_start_time": None,  # Reseting the process_start_time
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
            # Print the document ID for reference
            print(f"Document ID: {doc.id}")

            # Reference the document to update
            doc_ref = collection_ref.document(doc.id)

            # Update the document
            doc_ref.update(update_data)

    except Exception as e:
        print(f"Error updating process_mode for {file_path}", e)


def update_queue_status(
    file_path: str,
    status: str,
    output_uri: Optional[str] = None,
    error: Optional[Exception] = None,
) -> None:
    """
    Updates the processing status and related metadata for a document in Firestore.

    Args:
        file_path: GCS URI of the document
        status: New status ('processing', 'completed', or 'failed')
        output_uri: URI of the processed output
        error: Error information if processing failed

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


def get_sync_docs() -> List[firestore.DocumentSnapshot]:
    """
    Retrieves all documents marked for synchronous processing from Firestore.

    Returns:
        Firestore documents with process_mode='sync', ordered by added_time

    Note:
        Returns actual document objects, not just references
    """

    # Reference to the collection
    collection_ref = db.collection(FIRESTORE_COLLECTION)

    # Query documents where status is 'processing'
    query = collection_ref.where(
        filter=FieldFilter("process_mode", "==", "sync")
    ).order_by("added_time")
    docs = query.stream()

    docs_list = [doc for doc in docs]

    return docs_list


@functions_framework.http
def load_queue(request: Request) -> tuple[str, int]:
    """
    HTTP Cloud Function that initializes and starts document processing.

    Args:
        request: HTTP request object containing JSON payload
            with 'file_paths' list of GCS URIs

    Returns:
        Tuple of (response message, HTTP status code)

    Note:
        - Validates input format and content
        - Handles both individual files and folder paths
        - Initiates both sync and batch processing as needed
        - Returns 400 for invalid requests, 500 for processing errors
    """

    try:
        # Ensure the request contains JSON
        request_json = request.get_json(silent=True)

        if request_json is None:
            return "Invalid request, no JSON payload found", 400

        # Access the file_paths field from the JSON payload
        file_paths = request_json.get("file_paths")

        # Check if file_paths is a list
        if not isinstance(file_paths, list):
            return "file_paths should be a list", 400

        # Ensure the list is not empty
        if not file_paths or len(file_paths) == 0:
            return "file_paths list is empty", 400

        files = []
        for path in file_paths:
            if path.endswith("/"):
                bucket_name = path.split("/")[2]
                folder_name = "/".join(path.split("/")[3:])

                file_list = list_files_in_gcs_folder(bucket_name, folder_name)
                files.extend(file_list)
            else:
                files.append(path)

        # Add records to Firestore collection
        populate_queue(files)

        # Triggering the submit_batch cloud function manually for starting batch processing
        trigger_batch_processing()

        # Process all the sync files here
        docs = get_sync_docs()

        for doc in docs:
            file_path = doc.get("file_path")

            # Send online processing request
            print(f"Processing {file_path} ...")
            process_document_sync(file_path)

        return (
            "Queue populated successfully, Batch processing triggered and Sync processing is completed",
            200,
        )

    except Exception as e:
        print(f"Error processing the request: {e}")
        return "Error processing the request", 500
