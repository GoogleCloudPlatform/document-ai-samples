"""
Batch Process main.py
"""
# pylint: disable=E0401
# pylint: disable=C0301
# pylint: disable=R0913
# pylint: disable=R0917
# pylint: disable=C0325
# pylint: disable=W0718
# pylint: disable=R0801


import concurrent.futures
from io import StringIO
import time
from typing import List

import functions_framework
from google.api_core.operation import Operation
from google.cloud import documentai_v1beta3 as documentai
from google.cloud import storage
import pandas as pd


def batch_process_documents(
    project_id: str,
    location: str,
    processor_id: str,
    gcs_input_uri: str,
    gcs_output_uri: str,
) -> Operation:
    """
    Initiates a batch processing job using Document AI for documents stored in a GCS bucket.

    Args:
        project_id (str): Google Cloud project ID.
        location (str): Location of the processor ('us' or 'eu').
        processor_id (str): The ID of the Document AI processor.
        gcs_input_uri (str): The input folder path in GCS (must be a prefix).
        gcs_output_uri (str): The destination folder path in GCS for the output.
        timeout (int, optional): Time (in seconds) to wait for the operation to complete. Defaults to 600.

    Returns:
        operation (google.api_core.operation.Operation): The long-running operation instance for the batch job.
    """

    # You must set the api_endpoint if you use a location other than 'us', e.g.:
    opts = {}
    if location == "eu":
        opts = {"api_endpoint": "eu-documentai.googleapis.com"}
    elif location == "us":
        opts = {"api_endpoint": "us-documentai.googleapis.com"}
        # opts = {"api_endpoint": "us-autopush-documentai.sandbox.googleapis.com"}
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    input_config = documentai.BatchDocumentsInputConfig(
        gcs_prefix=documentai.GcsPrefix(gcs_uri_prefix=gcs_input_uri)
    )
    sharding_config = documentai.DocumentOutputConfig.GcsOutputConfig.ShardingConfig(
        pages_per_shard=10
    )
    gcs_output_config = documentai.DocumentOutputConfig.GcsOutputConfig(
        gcs_uri=gcs_output_uri, sharding_config=sharding_config
    )
    output_config = documentai.DocumentOutputConfig(gcs_output_config=gcs_output_config)

    # Location can be 'us' or 'eu'
    name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"
    request = documentai.types.document_processor_service.BatchProcessRequest(
        name=name,
        input_documents=input_config,
        document_output_config=output_config,
    )

    operation = client.batch_process_documents(request)

    # Wait for the operation to finish
    # operation.result(timeout=timeout)
    return operation


def list_folders(bucket_name: str, folder_prefix: str) -> List:
    """
    Lists all folder prefixes under a specified prefix in a GCS bucket.

    Args:
        bucket_name (str): Name of the GCS bucket.
        folder_prefix (str): GCS folder path prefix (e.g., 'output/processed/').

    Returns:
        List[str]: A list of folder prefixes found under the specified path.
    """

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    # List all objects with the given prefix
    blobs = bucket.list_blobs(prefix=folder_prefix, delimiter="/")

    folders = []
    for page in blobs.pages:
        folders.extend(page.prefixes)

    return folders


def batch_process_update(
    project_id: str,
    location: str,
    processor_id: str,
    batch_input_path: str,
    gcs_output_uri: str,
) -> List[dict]:
    """
    Runs a Document AI batch processor and waits for its completion.
    Then extracts metadata about input-output file mappings.

    Args:
        project_id (str): Google Cloud project ID.
        location (str): Location of the processor ('us' or 'eu').
        processor_id (str): The ID of the Document AI processor.
        batch_input_path (str): GCS path to the input documents (prefix).
        gcs_output_uri (str): GCS output path where results will be stored.

    Returns:
        List[dict]: A list of dictionaries containing source and destination paths
                    of processed documents.
    """

    res = batch_process_documents(
        project_id=project_id,
        location=location,
        processor_id=processor_id,
        gcs_input_uri=batch_input_path,
        gcs_output_uri=gcs_output_uri,
    )

    while not res.done():
        time.sleep(10)

    meta_data_dictionary = []
    for meta_data in res.metadata.individual_process_statuses:
        meta_data_dictionary.append(
            {
                "source": meta_data.input_gcs_source,
                "destination": meta_data.output_gcs_destination,
            }
        )

    return meta_data_dictionary


# Extract file names from the source URLs
def extract_file_name(source_url: str) -> str:
    """
    Extracts the file name from a GCS source URL.

    Args:
        source_url (str): The GCS path of the source file.

    Returns:
        str: The extracted file name.
    """

    return source_url.split("/")[-1]


# Create BigQuery client and update records
def update_bigquery(meta_data_bq: List, df: pd.DataFrame) -> pd.DataFrame:
    """
    Updates the given DataFrame with batch processed file paths and status
    based on the metadata returned from batch processing.

    Args:
        meta_data_bq (list): A nested list of dictionaries containing 'source' and 'destination' GCS paths.
        df (pd.DataFrame): The existing DataFrame to be updated.

    Returns:
        pd.DataFrame: The updated DataFrame with columns `Batch_processed_file_path` and `Batch_processed` updated.
    """
    # Flatten the list of lists into a single list
    flat_updates = [item for sublist in meta_data_bq for item in sublist]

    # Prepare updates
    updates_to_apply = []
    for update in flat_updates:
        # print(update)
        file_name = extract_file_name(update["source"])
        # print(file_name)
        batch_processed = "Yes" if len(update["destination"]) > 2 else "No"
        update_dict = {
            "File_name": file_name,
            "Batch_processed_file_path": update["destination"],
            "Batch_processed": batch_processed,
        }
        updates_to_apply.append(update_dict)

    # Perform updates
    for update in updates_to_apply:
        condition = df["File_name"] == update["File_name"]

        # Update the relevant columns based on the condition
        df.loc[condition, "Batch_processed_file_path"] = update[
            "Batch_processed_file_path"
        ]
        df.loc[condition, "Batch_processed"] = update["Batch_processed"]

    return df


def process_folder(
    folder: str,
    gcs_temp_path: str,
    project_id: str,
    location: str,
    processor_id: str,
    gcs_output_uri: str,
) -> List:
    """
    Initiates batch processing on a folder using the Document AI processor.

    Args:
        folder (str): Folder path inside the temp GCS bucket to process.
        gcs_temp_path (str): Full GCS path used as input for processing.
        project_id (str): GCP Project ID.
        location (str): Region where the processor is located.
        processor_id (str): ID of the Document AI processor.
        gcs_output_uri (str): Output GCS path to store results.

    Returns:
        list: Metadata dictionary containing 'source' and 'destination' paths.
    """
    gcs_temp_bucket_name = gcs_temp_path.split("/")[2]
    batch_input_path = f"gs://{gcs_temp_bucket_name}/{folder}"
    meta_data_dictionary = batch_process_update(
        project_id, location, processor_id, batch_input_path, gcs_output_uri
    )
    return meta_data_dictionary


@functions_framework.http
def concurrent_batch_process(request):
    """
    Cloud Function entry point for concurrently batch processing multiple folders
    using Document AI and updating the corresponding records in a DataFrame.

    Args:
        request (flask.Request): HTTP request containing parameters such as
            - project_id (str): GCP project ID
            - location (str): Region of the processor
            - processor_id (str): Document AI processor ID
            - gcs_temp_path (str): Input GCS path for processing
            - gcs_output_uri (str): Output GCS path for results
            - dataframe (str): JSON-serialized DataFrame to be updated

    Returns:
        Tuple[dict, int]: A JSON response and HTTP status code.
    """
    try:
        request_json = request.get_json(silent=True)
        if request_json:
            project_id = request_json.get("project_id")
            gcs_temp_path = request_json.get("gcs_temp_path")
            gcs_output_uri = request_json.get("gcs_output_uri")
            location = request_json.get("location")
            processor_id = request_json.get("processor_id")
            df = pd.read_json(StringIO(request_json.get("dataframe")), orient="records")
        else:
            project_id = request.args.get("project_id")
            gcs_temp_path = request.args.get("gcs_temp_path")
            gcs_output_uri = request.args.get("gcs_output_uri")
            location = request.args.get("location")
            processor_id = request.args.get("processor_id")
            df = pd.read_json(StringIO(request.args.get("dataframe")), orient="records")
        try:
            meta_data_bq = []
            gcs_temp_bucket_name = gcs_temp_path.split("/")[2]
            gcs_temp_folder_path = ("/").join(gcs_temp_path.split("/")[3:])
            folders = list_folders(gcs_temp_bucket_name, gcs_temp_folder_path)
            # Using ThreadPoolExecutor with 4 workers for parallel processing
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                # Submit tasks for each folder
                results = list(
                    executor.map(
                        lambda folder: process_folder(
                            folder,
                            gcs_temp_path,
                            project_id,
                            location,
                            processor_id,
                            gcs_output_uri,
                        ),
                        folders,
                    )
                )
            # Append results to meta_data_bq
            meta_data_bq.extend(results)
            # Define the dataset and table
            df = update_bigquery(meta_data_bq, df)

            return {
                "dataframe": df.to_json(orient="records"),
                "state": "DONE",
                "message": "BATCH PROCESSING AND DATAFRAME IS UPDATED",
            }, 200
        except Exception as e:
            return {"state": "FAILED", "message": f"Unable to process {e}"}, 500
    except Exception as e:
        return {
            "state": "FAILED",
            "message": f"Missing parameters needed to process the request {e}",
        }, 400
