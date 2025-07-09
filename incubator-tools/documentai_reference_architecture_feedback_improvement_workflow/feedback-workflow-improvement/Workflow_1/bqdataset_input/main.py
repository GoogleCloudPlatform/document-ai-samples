"""
Bigquery Dataset Input Main file
"""

# pylint: disable=E0401
# pylint: disable=W0718
# pylint: disable=W0612
# pylint: disable=R0801

from datetime import datetime
import functions_framework
from google.cloud import bigquery, storage
from google.api_core.exceptions import NotFound
import pandas as pd


def create_dataset_and_table(project_id : str, dataset_id : str,
                             table_id : str) -> None:

    """
    Creates a BigQuery dataset and table if they do not already exist.

    Args:
        project_id (str): GCP project ID.
        dataset_id (str): BigQuery dataset ID to check or create.
        table_id (str): BigQuery table ID to check or create.

    Returns:
        None. Prints the creation or existence status of the dataset and table.
    """
    client = bigquery.Client()

    # Dataset reference
    dataset_ref = client.dataset(dataset_id, project=project_id)
    table_ref = dataset_ref.table(table_id)

    try:
        # Check if dataset exists
        client.get_dataset(dataset_ref)
        print(f"Dataset '{dataset_id}' exists.")

        # Check if the table exists
        try:
            client.get_table(table_ref)
            print(f"Table '{table_id}' exists in dataset '{dataset_id}'.")
        except NotFound:
            print(f"Table '{table_id}' does not exist in dataset '{dataset_id}', creating table...")
            schema = [
                bigquery.SchemaField("File_name", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("GCS_folder_path", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("Batch_processed", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("Batch_processed_file_path", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("HITL_checked", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("HITL_criteria_passed", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("HITL_folder_path", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED")
            ]
            table = bigquery.Table(table_ref, schema=schema)
            client.create_table(table)
            print(f"Table '{table_id}' created in dataset '{dataset_id}'.")
    except NotFound:
        print(f"Dataset '{dataset_id}' does not exist, creating dataset and table...")
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        client.create_dataset(dataset)
        print(f"Dataset '{dataset_id}' created.")
        schema = [
            bigquery.SchemaField("File_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("GCS_folder_path", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("Batch_processed", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("Batch_processed_file_path", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("HITL_checked", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("HITL_criteria_passed", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("HITL_folder_path", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED")
        ]
        table = bigquery.Table(table_ref, schema=schema)
        client.create_table(table)
        print(f"Table '{table_id}' created in dataset '{dataset_id}'.")


def list_and_insert_gcs_files(project_id : str, dataset_id : str,
                              table_id : str, gcs_input_path : str) -> pd.DataFrame:

    """
    Lists all files in a GCS folder and prepares a DataFrame with metadata
    to insert into a BigQuery table.

    Args:
        project_id (str): GCP project ID.
        dataset_id (str): BigQuery dataset ID.
        table_id (str): BigQuery table ID.
        gcs_input_path (str): GCS path in the format 'gs://bucket/folder/...'.

    Returns:
        pandas.DataFrame: A DataFrame containing metadata for each file, ready for BigQuery.
    """
    bigquery_client = bigquery.Client()
    storage_client = storage.Client()

    gcs_bucket_name = gcs_input_path.split('/')[2]
    gcs_folder_path = '/'.join(gcs_input_path.split('/')[3:])

    def list_gcs_files(bucket_name, folder_path):
        bucket = storage_client.bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=folder_path)
        files = [blob.name for blob in blobs if not blob.name.endswith("/")]
        return files

    files = list_gcs_files(gcs_bucket_name, gcs_folder_path)

    dataset_ref = bigquery_client.dataset(dataset_id, project=project_id)
    table_ref = dataset_ref.table(table_id)
    print(table_ref)

    rows_to_insert = [
        {
            "File_name": file.split("/")[-1],
            "GCS_folder_path": f"gs://{gcs_bucket_name}/{gcs_folder_path}",
            "Batch_processed": "No",
            "Batch_processed_file_path": "NA",
            "HITL_checked": "No",
            "HITL_criteria_passed": "NA",
            "HITL_folder_path": "NA",
            "timestamp": datetime.now().isoformat()
        }
        for file in files
    ]

    df = pd.DataFrame(rows_to_insert)
    return df


@functions_framework.http
def bqdataset(request):

    """
    Cloud Function HTTP handler to create a BigQuery dataset and table,
    and populate it with metadata from files in a GCS path.

    Expects the following parameters either in JSON body or query string:
        - project_id (str): GCP project ID.
        - dataset_id (str): BigQuery dataset ID.
        - table_id (str): BigQuery table ID.
        - gcs_input_path (str): GCS path to list files from.

    Args:
        request (flask.Request): The incoming HTTP request object.

    Returns:
        Tuple[Dict, int]: JSON response with dataframe (as JSON) and a status code.
                          Returns 200 on success, 400/500 on failure.
    """
    try:
        request_json = request.get_json(silent=True)
        if request_json:
            project_id = request_json.get("project_id")
            dataset_id = request_json.get("dataset_id")
            table_id = request_json.get("table_id")
            gcs_input_path = request_json.get("gcs_input_path")
        else:
            project_id = request.args.get("project_id")
            dataset_id = request.args.get("dataset_id")
            table_id = request.args.get("table_id")
            gcs_input_path = request.args.get("gcs_input_path")

        try:
            create_dataset_and_table(project_id, dataset_id, table_id)
            df = list_and_insert_gcs_files(project_id, dataset_id, table_id, gcs_input_path)
            print(df)
            return {
                "dataframe": df.to_json(orient="records"),
                "state": "DONE",
                "message": "Dataset is created and file details added to BigQuery table"
            }, 200
        except Exception as e:
            print(e)
            return {
                "state": "FAILED",
                "message": f"Unable to complete due to: {e}"
            }, 500
    except Exception as e:
        print(e)
        return {
            "state": "FAILED",
            "message": f"Unable to get needed parameters: {e}"
        }, 400
