"""
Confidence level (by default all entities are considered). Critical entities & Confidence level
"""

# pylint: disable=E0401
# pylint: disable=W0718
# pylint: disable=R0917
# pylint: disable=R0914
# pylint: disable=R0913
# pylint: disable=W0613
# pylint: disable=C0121
# pylint: disable=R0801

import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
import os
import random
from typing import Any, Dict, List, Tuple

import functions_framework
from google.cloud import bigquery
from google.cloud import documentai_v1beta3 as documentai
from google.cloud import storage
import pandas as pd


def documentai_json_proto_downloader(
    bucket_name: str, blob_name_with_prefix_path: str
) -> object:
    """
    Downloads a file from a specified Google Cloud Storage bucket
    and converts it into a DocumentAI Document proto.

    Args:
        bucket_name (str): The name of the GCS bucket from which to download the file.
        blob_name_with_prefix_path (str): The full path (prefix) to the JSON blob in the bucket.

    Returns:
        documentai.Document: A DocumentAI Document proto representation of the downloaded JSON.
    """

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name_with_prefix_path)

    doc = documentai.Document.from_json(blob.download_as_bytes())

    return doc


def copy_folder(source_path: str, destination_path: str, file_name: str) -> None:
    """
    Copying files from source bukcet to destination bucket
    """

    # Initialize the Google Cloud Storage client
    storage_client = storage.Client()
    # Extract source bucket and folder
    source_bucket_name = source_path.split("/")[2]
    source_folder = "/".join(source_path.split("/")[3:]) + "/"
    # Extract destination bucket and folder
    destination_bucket_name = destination_path.split("/")[2]
    destination_folder = (
        "/".join(destination_path.split("/")[3:]) + file_name.rsplit(".", 1)[0]
    )
    # Get the source and destination buckets
    source_bucket = storage_client.bucket(source_bucket_name)
    destination_bucket = storage_client.bucket(destination_bucket_name)

    # Ensure the destination folder ends with a '/'
    if not destination_folder.endswith("/"):
        destination_folder += "/"

    # List all blobs in the source folder
    blobs = source_bucket.list_blobs(prefix=source_folder)

    for blob in blobs:
        # Construct the new blob name for the destination
        # Including the folder name in the destination path
        relative_path = os.path.relpath(blob.name, source_folder)
        new_blob_name = os.path.join(destination_folder, relative_path)

        # Copy the blob
        destination_bucket.copy_blob(blob, destination_bucket, new_blob_name)
        # print(f'Blob {blob.name} copied to {new_blob_name}.')


def list_gcs_files_with_uri(bucket_name: str, folder_uri: str) -> List:
    """
    Returns all the files present inside the bucket.
    """
    # Initialize a Google Cloud Storage client
    client = storage.Client()

    # Access the bucket
    bucket = client.bucket(bucket_name)

    # List all objects in the given folder
    blobs = bucket.list_blobs(prefix=f"{folder_uri}/")

    # Print the files found with full GCS URI
    files = []
    for blob in blobs:
        # Create full GCS URI
        full_uri = f"gs://{bucket_name}/{blob.name}"
        files.append(full_uri)

    return files


def criteria_check(
    json_data: dict[Any, Any], confidence_threshold: float, critical_entities: List
) -> bool:
    """
    Check if the entities in the JSON data meet the confidence threshold criteria.

    Args:
        json_data (Dict): The JSON data containing entities and their properties.
        confidence_threshold (float): The minimum confidence score required.
        critical_entities (list): List of entity types considered critical.

    Returns:
        bool: True if all entities meet the criteria, False otherwise.
    """

    hitl_criteria_satisfied = True
    if len(critical_entities) > 0:
        for entity in json_data.entities:
            if entity.type in critical_entities:
                if entity.confidence < confidence_threshold:
                    hitl_criteria_satisfied = False
                    return hitl_criteria_satisfied
            for sub_entity in entity.properties:
                if sub_entity.type in critical_entities:
                    if sub_entity.confidence < confidence_threshold:
                        hitl_criteria_satisfied = False
                        return hitl_criteria_satisfied
    else:
        for entity in json_data.entities:
            if entity.confidence < confidence_threshold:
                hitl_criteria_satisfied = False
                return hitl_criteria_satisfied
            for sub_entity in entity.properties:
                if sub_entity.confidence < confidence_threshold:
                    hitl_criteria_satisfied = False
                    return hitl_criteria_satisfied
    return hitl_criteria_satisfied


# Define the function for processing a single file
def process_file(
    file: dict,
    dataset_id: str,
    table_id: str,
    confidence_threshold: float,
    critical_entities: List,
    gsc_hitl_folder_path: str,
) -> Tuple:
    """
    Process a single file and determine if it passes the HITL criteria.

    Args:
        file (dict): Dictionary containing file information.
        dataset_id (str): ID of the dataset.
        table_id (str): ID of the table.
        confidence_threshold (float): The minimum confidence score required.
        critical_entities (list): List of entity types considered critical.
        gsc_hitl_folder_path (str): Path to the HITL folder in Google Cloud Storage.

    Returns:
        tuple: Two lists containing passed and failed files respectively.
    """
    hitl_passed = []
    hitl_failed = []

    bucket_name_1 = file["file_path"].split("/")[2]
    folder_uri = "/".join(file["file_path"].split("/")[3:])
    list_files = list_gcs_files_with_uri(bucket_name_1, folder_uri)
    hitl_check_status = True
    for f1 in list_files:
        source_path_1 = "/".join(f1.rsplit("/", 1)[:-1])
        if file["file_name"].rsplit(".", 1)[0] in f1:
            json_data = documentai_json_proto_downloader(
                f1.split("/")[2], "/".join(f1.split("/")[3:])
            )
            if not criteria_check(json_data, confidence_threshold, critical_entities):
                copy_folder(source_path_1, gsc_hitl_folder_path, file["file_name"])
                hitl_temp_path = os.path.join(
                    gsc_hitl_folder_path, file["file_name"].rsplit(".", 1)[0]
                )
                hitl_check_status = False
                break

    if hitl_check_status:
        print("PASSED", file["file_name"])
        hitl_passed.append(
            {
                "file_name": file["file_name"],
                "batch_processed_path": file["file_path"],
                "hitl_path": "",
            }
        )
    elif not hitl_check_status:
        print("Failed", file["file_name"])
        hitl_failed.append(
            {
                "file_name": file["file_name"],
                "batch_processed_path": file["file_path"],
                "hitl_path": hitl_temp_path,
            }
        )

    return hitl_passed, hitl_failed


# Define the main function to handle parallel processing
def process_files_in_parallel(
    dataset_id: str,
    table_id: str,
    confidence_threshold: float,
    critical_entities: List,
    gsc_hitl_folder_path: str,
    df: pd.DataFrame,
) -> Tuple:
    """
    Process multiple files in parallel to check HITL criteria.

    Args:
        dataset_id (str): ID of the dataset.
        table_id (str): ID of the table.
        confidence_threshold (float): The minimum confidence score required.
        critical_entities (list): List of entity types considered critical.
        gsc_hitl_folder_path (str): Path to the HITL folder in Google Cloud Storage.
        df (pandas.DataFrame): DataFrame containing file information.

    Returns:
        tuple: Two lists containing all passed and failed files respectively.
    """

    filtered_df = df[df["Batch_processed"].str.strip().str.upper() == "YES"][
        ["File_name", "Batch_processed_file_path"]
    ]
    file_data = [
        {"file_name": row["File_name"], "file_path": row["Batch_processed_file_path"]}
        for index, row in filtered_df.iterrows()
    ]

    all_hitl_passed = []
    all_hitl_failed = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        # Prepare the arguments for each file
        futures = {
            executor.submit(
                process_file,
                file,
                dataset_id,
                table_id,
                confidence_threshold,
                critical_entities,
                gsc_hitl_folder_path,
            ): file
            for file in file_data
        }

        for future in concurrent.futures.as_completed(futures):
            try:
                hitl_passed, hitl_failed = future.result()
                all_hitl_passed.extend(hitl_passed)
                all_hitl_failed.extend(hitl_failed)
            except Exception as exc:
                print(f"File processing generated an exception: {exc}")

    return all_hitl_passed, all_hitl_failed


def copy_selected_files(
    hitl_passed: List,
    gsc_hitl_folder_path: str,
    percentage: int = 10,
    max_workers: int = 4,
):
    """
    Copy a random selection of passed files to the HITL folder.

    Args:
        hitl_passed (list): List of files that passed HITL criteria.
        gsc_hitl_folder_path (str): Path to the HITL folder in Google Cloud Storage.
        percentage (int): Percentage of files to select for copying.
        max_workers (int): Maximum number of concurrent workers for file copying.

    Returns:
        None
    """
    # Define the number of files to select based on the percentage
    num_files_to_select = round(len(hitl_passed) * percentage / 100)
    print("num_files_to_select", num_files_to_select)

    # Randomly select the files
    selected_files = random.sample(hitl_passed, num_files_to_select)

    def process_files(file):
        source_path = file["batch_processed_path"]

        # Perform folder copying
        copy_folder(source_path, gsc_hitl_folder_path, file["file_name"])

        # Construct the hitl_temp_path
        if gsc_hitl_folder_path.endswith("/"):
            hitl_temp_path = (
                gsc_hitl_folder_path + file["file_name"].rsplit(".", 1)[0] + "/"
            )
        else:
            hitl_temp_path = (
                gsc_hitl_folder_path + "/" + file["file_name"].rsplit(".", 1)[0] + "/"
            )

        # Update the hitl_path in hitl_passed
        for i1 in hitl_passed:
            if i1["batch_processed_path"] == file["batch_processed_path"]:
                i1["hitl_path"] = hitl_temp_path

    # Use ThreadPoolExecutor to process files concurrently
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(process_files, selected_files)

    # return hitl_passed


@functions_framework.http
def hitl_feedback(request):
    """
    Cloud Function to handle HITL feedback process.

    Returns:
        tuple: A tuple containing a dictionary with process results and an HTTP status code.
    """
    try:
        request_json = request.get_json(silent=True)
        if request_json:
            project_id = request_json.get("project_id")
            dataset_id = request_json.get("dataset_id")
            table_id = request_json.get("table_id")
            gsc_hitl_folder_path = request_json.get("Gcs_HITL_folder_path")
            confidence_threshold = request_json.get("confidence_threshold")
            critical_entities = request_json.get("critical_entities")
            test_files_percentage = request_json.get("test_files_percentage")
            df = pd.read_json(StringIO(request_json.get("dataframe")), orient="records")
        else:
            project_id = request.args.get("project_id")
            dataset_id = request.args.get("dataset_id")
            table_id = request.args.get("table_id")
            gsc_hitl_folder_path = request.args.get("Gcs_HITL_folder_path")
            confidence_threshold = request.args.get("confidence_threshold")
            critical_entities = request.args.get("critical_entities")
            test_files_percentage = request.args.get("test_files_percentage")
            df = pd.read_json(StringIO(request.args.get("dataframe")), orient="records")
        try:
            table_ref = f"{project_id}.{dataset_id}.{table_id}"
            hitl_passed, hitl_failed = process_files_in_parallel(
                dataset_id,
                table_id,
                confidence_threshold,
                critical_entities,
                gsc_hitl_folder_path,
                df,
            )

            copy_selected_files(
                hitl_passed,
                gsc_hitl_folder_path,
                percentage=test_files_percentage,
                max_workers=4,
            )
            for update_p in hitl_passed:
                condition = (df["File_name"] == update_p["file_name"]) & (
                    df["Batch_processed_file_path"] == update_p["batch_processed_path"]
                )

                # Update the relevant columns based on the condition
                df.loc[condition, "HITL_folder_path"] = update_p["hitl_path"]
                df.loc[condition, "HITL_criteria_passed"] = "YES"
                df.loc[condition, "HITL_checked"] = "YES"
            for update_f in hitl_failed:
                condition = (df["File_name"] == update_f["file_name"]) & (
                    df["Batch_processed_file_path"] == update_f["batch_processed_path"]
                )
                # Update the relevant columns based on the condition
                df.loc[condition, "HITL_folder_path"] = update_f["hitl_path"]
                df.loc[condition, "HITL_criteria_passed"] = "NO"
                df.loc[condition, "HITL_checked"] = "YES"

            client = bigquery.Client()
            job = client.load_table_from_dataframe(
                df,
                table_ref,
                job_config=bigquery.LoadJobConfig(
                    source_format=bigquery.SourceFormat.PARQUET
                ),
            )
            # job = client.load_table_from_dataframe(df, table_ref)
            job.result()

            return {
                "dataframe": df.to_json(orient="records"),
                "state": "DONE",
                "message": "HITL Criteria checked and moved to folder",
            }, 200
        except Exception as e:
            print(e)
            return {
                "state": "FAILED",
                "message": f"Unable to complete HITL criteria check because of {e}",
            }, 500
    except Exception as e:
        print(e)
        return {
            "state": "FAILED",
            "message": f"Missing parameters need to process the request because of {e}",
        }, 400
