from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import uuid

from google.cloud import bigquery
from google.cloud import documentai
from google.cloud import storage


def file_names(gs_input_file_path):
    bucket = gs_input_file_path.split("/")[2]
    file_names_list = []
    file_dict = {}

    storage_client = storage.Client()
    source_bucket = storage_client.get_bucket(bucket)

    filenames = [
        filename.name
        for filename in list(
            source_bucket.list_blobs(
                prefix=(("/").join(gs_input_file_path.split("/")[3:]))
            )
        )
    ]

    for i, _ in enumerate(filenames):
        x = filenames[i].split("/")[-1]
        if x:
            file_names_list.append(x)
            file_dict[x] = filenames[i]

    return file_names_list, file_dict


def store_document_as_json(
    document, bucket_name: str, file_name: str, encoding="utf-8"
):
    """
    Store Document json in cloud storage.
    """

    storage_client = storage.Client()
    process_result_bucket = storage_client.get_bucket(bucket_name)
    document_blob = storage.Blob(
        name=str(Path(file_name)), bucket=process_result_bucket
    )
    document_blob.upload_from_string(
        document.encode(encoding), content_type="application/json"
    )


def batch_process_documents(
    project_id,
    location,
    processor_id,
    processor_version_id,
    gcs_input_uri,
    gcs_output_uri,
    gcs_output_uri_prefix,
    canonical_bucket_name,
    timeout: int = 6000,
):
    from google.api_core.exceptions import InternalServerError
    from google.api_core.exceptions import RetryError
    from google.cloud import documentai_v1beta3 as documentai

    # You must set the api_endpoint if you use a location other than 'us', e.g.:
    opts = {}
    if location == "eu":
        opts = {"api_endpoint": "eu-documentai.googleapis.com"}
    elif location == "us":
        opts = {"api_endpoint": "us-documentai.googleapis.com"}

    client = documentai.DocumentProcessorServiceClient(client_options=opts)

    destination_uri = f"{gcs_output_uri}/{gcs_output_uri_prefix}/"

    gcs_documents = documentai.GcsDocuments(documents=gcs_input_uri)

    input_config = documentai.BatchDocumentsInputConfig(gcs_documents=gcs_documents)

    sharding_config = documentai.DocumentOutputConfig.GcsOutputConfig.ShardingConfig(
        pages_per_shard=200
    )

    gcs_output_config = documentai.DocumentOutputConfig.GcsOutputConfig(
        gcs_uri=destination_uri, sharding_config=sharding_config
    )

    output_config = documentai.DocumentOutputConfig(gcs_output_config=gcs_output_config)

    # Location can be 'us' or 'eu'
    name = f"projects/{project_id}/locations/{location}/processors/{processor_id}/processorVersions/{processor_version_id}"
    request = documentai.types.document_processor_service.BatchProcessRequest(
        name=name,
        input_documents=input_config,
        document_output_config=output_config,
    )

    operation = client.batch_process_documents(request)

    try:
        operation.result(timeout=timeout)
    except (RetryError, InternalServerError) as e:
        print(e.message)

    metadata = documentai.BatchProcessMetadata(operation.metadata)
    if metadata.state != documentai.BatchProcessMetadata.State.SUCCEEDED:
        raise ValueError(f"Batch Process Failed: {metadata.state_message}")
    return metadata, operation.operation.name.split("/")[-1]


def create_bigquery(project_name, dataset_name, table_name):
    client = bigquery.Client()
    table_id = f"{project_name}.{dataset_name}.{table_name}"
    schema = [
        bigquery.SchemaField(name="File_name", field_type="STRING", mode="NULLABLE"),
        bigquery.SchemaField(name="Raw_pdf_path", field_type="STRING", mode="NULLABLE"),
        bigquery.SchemaField(
            name="Parsed_jsons_path", field_type="STRING", mode="NULLABLE"
        ),
        bigquery.SchemaField(
            name="Canonical_jsons_path", field_type="STRING", mode="NULLABLE"
        ),
        bigquery.SchemaField(
            name="Metadata_Jsonl_file", field_type="STRING", mode="NULLABLE"
        ),
        bigquery.SchemaField(name="Status", field_type="STRING", mode="NULLABLE"),
    ]
    # Check if the table already exists
    try:
        client.get_table(table_id)
        return f"Table {table_id} already exists.", schema
    except Exception as e:
        # Table does not exist, proceed with creating it
        table = bigquery.Table(table_id, schema=schema)
        table._properties["tableConstraints"] = {}
        table._properties["tableConstraints"]["primaryKey"] = {"columns": ["File_name"]}

        try:
            table = client.create_table(table)
            return f"Created table {table_id}.", schema
        except Exception as e:
            return f"Error: {str(e)}"


def copy_blob(
    bucket_name: str,
    blob_name: str,
    destination_bucket_name: str,
    destination_blob_name: str,
) -> None:
    """
    Copies a blob (file/object) from one GCP storage bucket to another.

    Args:
        bucket_name (str): Name of the source bucket.
        blob_name (str): Name of the blob (file/object) in the source bucket to be copied.
        destination_bucket_name (str): Name of the destination bucket.
        destination_blob_name (str): Desired name for the blob in the destination bucket.

    Output:
        None. The blob is copied to the destination bucket with the specified name.
    """
    storage_client = storage.Client()
    source_bucket = storage_client.bucket(bucket_name)
    source_blob = source_bucket.blob(blob_name)
    destination_bucket = storage_client.bucket(destination_bucket_name)
    source_bucket.copy_blob(source_blob, destination_bucket, destination_blob_name)


def delete_blob(bucket_name: str, blob_name: str) -> None:
    """
    Deletes a blob (file/object) from GCP storage Bucket.

    Args:
        bucket_name (str): Name of the source bucket.
        blob_name (str): Name of the blob (file/object) in the source bucket to be copied.

    Output:
        None. The blob is copied to the destination bucket with the specified name.
    """
    storage_client = storage.Client()
    source_bucket = storage_client.bucket(bucket_name)
    source_blob = source_bucket.blob(blob_name)
    source_blob.delete()


def create_folder_in_bucket(bucket_name: str, folder_name: str):
    """
    Create a folder-like structure (subdirectory) inside the specified Google Cloud Storage bucket.

    Args:
        bucket_name (str): The name of the bucket.
        folder_name (str): The name of the folder to create.

    Returns:
        None
    """
    print("create_folder_in_bucket")
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    # Check if the folder already exists
    if not blob_exists(bucket, folder_name):
        # Create an empty blob (object) with the folder name as a prefix
        blob = bucket.blob(f"{folder_name}/")
        blob.upload_from_string("")  # Empty content

        print(
            f"Folder '{folder_name}' created successfully in bucket '{bucket_name}' and path is {bucket_name}/{folder_name}"
        )
    else:
        print(f"Folder '{folder_name}' already exists in bucket '{bucket_name}'")


def blob_exists(bucket, prefix):
    """Check if a blob with the given prefix exists in the bucket."""
    blobs = bucket.list_blobs(prefix=prefix)
    return any(True for _ in blobs)


def func1_batch(
    newly_added_files,
    table_id,
    input_bucket_name,
    parsed_bucket_name,
    canonical_bucket_name,
    jsonl_bucket_path,
    gs_input_file_path,
    project_id,
    location,
    processor_id,
    processor_version_id,
    schema,
):
    create_folder_in_bucket(canonical_bucket_name, "batch_status")
    create_folder_in_bucket(canonical_bucket_name, "batch_status/Success")
    create_folder_in_bucket(canonical_bucket_name, "batch_status/Failure")

    original_files_list, original_files_dict = file_names(gs_input_file_path)
    batch_input_paths = []
    for file1 in newly_added_files:
        if file1 in original_files_list:
            batch_input_paths.append(
                f"gs://{input_bucket_name}/{original_files_dict[file1]}"
            )
    print("Batch_input_paths : ", batch_input_paths)
    print("Newly_Added_Files_to_process : ", newly_added_files)

    import pandas as pd

    df = pd.DataFrame(
        columns=[
            "File_name",
            "Raw_pdf_path",
            "Parsed_jsons_path",
            "Canonical_jsons_path",
            "Metadata_Jsonl_file",
            "Status",
        ]
    )

    start = 0
    end = len(newly_added_files)
    step = 50
    for i in range(start, end, step):
        x = i
        process_batch_array = batch_input_paths[x : x + step]
        print("process_batch_array : ", process_batch_array)
        status_of_file = "Failure"
        documents = []
        for uri in process_batch_array:
            if str(uri).endswith(".pdf"):
                documents.append({"gcs_uri": uri, "mime_type": "application/pdf"})
            elif str(uri).endswith(".png"):
                documents.append({"gcs_uri": uri, "mime_type": "image/png"})
            elif str(uri).endswith(".jpeg"):
                documents.append({"gcs_uri": uri, "mime_type": "image/jpeg"})
            elif str(uri).endswith(".jpg"):
                documents.append({"gcs_uri": uri, "mime_type": "image/jpeg"})
            elif str(uri).endswith(".tiff"):
                documents.append({"gcs_uri": uri, "mime_type": "image/tiff"})
            elif str(uri).endswith(".tif"):
                documents.append({"gcs_uri": uri, "mime_type": "image/tiff"})
            else:
                print("Unsupported File", uri)
                temp_bucket_name = uri.split("/")[2]
                temp_blob = "/".join(uri.split("/")[3:])
                print(temp_bucket_name)
                print(temp_blob)
                copy_blob(
                    temp_bucket_name,
                    temp_blob,
                    canonical_bucket_name,
                    f"batch_status/Failure/{temp_blob}",
                )
                rowdata = {
                    "File_name": uri.split("/")[-1],
                    "Raw_pdf_path": "NA",
                    "Parsed_jsons_path": "NA",
                    "Canonical_jsons_path": "NA",
                    "Status": status_of_file,
                }
                # df = df.append(rowdata, ignore_index=True)
                df = pd.concat([df, pd.DataFrame([rowdata])], ignore_index=True)
                delete_blob(temp_bucket_name, temp_blob)

        print(documents)

        try:
            metalist = []
            print("Batch Processing........")
            if len(documents) >= 1:
                metadata, operation = batch_process_documents(
                    project_id="rand-automl-project",
                    location="us",
                    processor_id="7fbb1ccb4dff7b3c",
                    processor_version_id="pretrained-invoice-v2.0-2023-12-06",
                    gcs_input_uri=documents,
                    gcs_output_uri="gs://"
                    + parsed_bucket_name
                    + f"/temp_processor_output",
                    gcs_output_uri_prefix="output",
                    canonical_bucket_name=canonical_bucket_name,
                    timeout=500,
                )
                print("HHAIIII")
                batch_status = True
                if metadata.individual_process_statuses:
                    for j in metadata.individual_process_statuses:
                        gcs_input_source = j.input_gcs_source
                        if j.output_gcs_destination:
                            print("Processing File........", gcs_input_source)
                            print("Move to Sucess Folder.....")
                            bucket_source = gcs_input_source.split("/")[2]
                            blob_source = "/".join(gcs_input_source.split("/")[3:])
                            copy_blob(
                                bucket_source,
                                blob_source,
                                canonical_bucket_name,
                                f"batch_status/Success/{gcs_input_source.split('/')[-1]}",
                            )
                            print(
                                f"Copied from {bucket_source}/{blob_source} to {canonical_bucket_name}/batch_status/Success/{gcs_input_source.split('/')[-1]}"
                            )
                            delete_blob(bucket_source, blob_source)
                            print("Deleted the blob", blob_source)
                            status_of_file = "Success"
                            gcs_output_destination = j.output_gcs_destination
                            bucket_name = gcs_output_destination.split("/")[2]
                            prefix = "/".join(gcs_output_destination.split("/")[3:])
                            client1 = storage.Client()
                            blobs = list(
                                client1.list_blobs(
                                    bucket_or_name=bucket_name, prefix=prefix
                                )
                            )
                            conanical_json = {}
                            file_name = gcs_input_source.split("/")[-1]
                            conanical_json["title"] = file_name
                            conanical_json["blocks"] = list()
                            page_no = 0
                            for k in blobs:
                                doc_json = documentai.Document.from_json(
                                    k.download_as_string()
                                )
                                if doc_json.text:
                                    OCR_text = doc_json.text
                                    if doc_json.pages:
                                        if doc_json.pages[0].layout:
                                            for page in doc_json.pages:
                                                a = {}
                                                a["textBlock"] = {}
                                                a["textBlock"]["text"] = OCR_text[
                                                    page.layout.text_anchor.text_segments[
                                                        0
                                                    ]
                                                    .start_index : page.layout.text_anchor.text_segments[
                                                        0
                                                    ]
                                                    .end_index
                                                ]
                                                a["textBlock"]["type"] = "PARAGRAPH"
                                                a["pageNumber"] = page.page_number
                                                conanical_json["blocks"].append(a)
                                        else:
                                            a["textBlock"] = {}
                                            a["textBlock"]["text"] = doc_json.text
                                            a["textBlock"]["type"] = "PARAGRAPH"
                                            a["pageNumber"] = 1
                                            conanical_json["blocks"].append(a)
                            store_document_as_json(
                                json.dumps(conanical_json),
                                canonical_bucket_name,
                                f"canonical_object/{file_name}.json",
                            )
                            print(
                                "Canonical Json Created......",
                                f"{canonical_bucket_name}/canonical_object/{file_name}.json",
                            )

                            metadata_schema = {
                                "id": "your_random_id",
                                "structData": {
                                    "Title": "File Title",
                                    "Source_url": "https://storage.mtls.cloud.google.com/",
                                },
                                "content": {
                                    "mimeType": "application/json",
                                    "uri": "gs://",
                                },
                            }
                            metadata_json_copy = deepcopy(metadata_schema)
                            metadata_json_copy["id"] = str(uuid.uuid4())
                            metadata_json_copy["content"][
                                "uri"
                            ] += f"{canonical_bucket_name}/canonical_object/{file_name}.json"
                            metadata_json_copy["structData"]["Source_url"] += (
                                canonical_bucket_name
                                + f"/batch_status/Success/{file_name}"
                            )
                            metadata_json_copy["structData"]["Title"] = file_name
                            for meta in blobs:
                                doc_json = documentai.Document.from_json(
                                    meta.download_as_string()
                                )
                                for entity in doc_json.entities:
                                    metadata_json_copy["structData"][
                                        entity.type_
                                    ] = entity.mention_text
                                single_metadata = json.dumps(metadata_json_copy)

                            metalist.append(single_metadata)

                            rowdata = {
                                "File_name": f"{file_name}",
                                "Raw_pdf_path": gcs_input_source,
                                "Parsed_jsons_path": f"{gcs_output_destination}",
                                "Canonical_jsons_path": f"gs://{canonical_bucket_name}/canonical_object/{file_name}.json",
                                "Status": status_of_file,
                            }
                            # df = df.append(rowdata, ignore_index=True)
                            df = pd.concat(
                                [df, pd.DataFrame([rowdata])], ignore_index=True
                            )
                        else:
                            print("Failed Files.........", gcs_input_source)
                            print("Moved to Failed Folder.......")
                            bucket_source = gcs_input_source.split("/")[2]
                            blob_source = "/".join(gcs_input_source.split("/")[3:])
                            copy_blob(
                                bucket_source,
                                blob_source,
                                canonical_bucket_name,
                                f"batch_status/Failure/{gcs_input_source.split('/')[-1]}",
                            )
                            delete_blob(bucket_source, blob_source)
                            status_of_file = "Failure"
                            continue

                    merge_meta = ""
                    for item in metalist:
                        merge_meta += item + "\n"
                    import time

                    current_timestamp = int(time.time())
                    jsonl_bucket_name = jsonl_bucket_path.split("/")[2]
                    time = current_timestamp
                    store_document_as_json(
                        merge_meta, jsonl_bucket_name, f"metadatajsonl_{time}.jsonl"
                    )
                    store_document_as_json(
                        merge_meta,
                        canonical_bucket_name,
                        f"jsonl_metadata/metadatajsonl_{current_timestamp}.jsonl",
                    )

                    timestamp_appended_filename = (
                        f"metadatajsonl_{current_timestamp}.jsonl"
                    )
                    full_path = f"gs://{canonical_bucket_name}/jsonl_metadata/{timestamp_appended_filename}"
                    print("Metadata Jsonl Path......", full_path)

                    for meta in newly_added_files[x : x + step]:
                        print(meta)
                        print(df["File_name"].values)
                        if meta in df["File_name"].values:
                            df.loc[
                                df["File_name"] == meta, "Metadata_Jsonl_file"
                            ] = full_path
            else:
                print("No documents found")

        except Exception as e:
            print(f"Error :", e)

    print("Final Dataframe :")
    print(df)
    client = bigquery.Client()
    job_config = bigquery.LoadJobConfig(schema=schema)
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)


def check_and_insert_files(
    project_name,
    dataset_name,
    table_name,
    gs_input_file_path,
    parsed_json_path,
    canonical_json_path,
    jsonl_bucket_path,
    project_id,
    location,
    processor_id,
    processor_version_id,
    schema,
):
    client = bigquery.Client()
    table_id = f"{project_name}.{dataset_name}.{table_name}"

    # Get the list of files from the Google Cloud Storage path
    file_names_list, file_dict = file_names(gs_input_file_path)
    # Buckets Names
    input_bucket_name = gs_input_file_path.split("/")[2]
    parsed_bucket_name = parsed_json_path.split("/")[2]
    canonical_bucket_name = canonical_json_path.split("/")[2]
    # Getting files from both the buckets
    file_names_list_parsed, file_dict_parsed = file_names(parsed_json_path)
    file_names_list_canonical, file_dict_canonical = file_names(canonical_json_path)

    # Check and insert files into BigQuery
    newly_added_files = []
    for file_name in file_names_list:
        # Check if the file is already present in BigQuery
        query = f"SELECT File_name FROM `{table_id}` WHERE File_name = '{file_name}'"
        query_job = client.query(query)

        if not list(query_job):
            # File is not present, insert it into BigQuery
            newly_added_files.append(file_name)
        else:
            print(f"File {file_name} is already present in BigQuery.")
            copy_blob(
                input_bucket_name,
                file_dict[file_name],
                canonical_bucket_name,
                f"batch_status/Existing/{file_name}",
            )
            print(
                f"Copied from {input_bucket_name}/{file_dict[file_name]} to {canonical_bucket_name}/batch_status/Existing/{file_name}"
            )
            delete_blob(input_bucket_name, file_dict[file_name])
    try:
        func1_batch(
            newly_added_files,
            table_id,
            input_bucket_name,
            parsed_bucket_name,
            canonical_bucket_name,
            jsonl_bucket_path,
            gs_input_file_path,
            project_id,
            location,
            processor_id,
            processor_version_id,
            schema,
        )

    except Exception as e:
        print("Exception :", e)

    return newly_added_files


def pdf_jsonl(request):
    print(request)
    request_json = request.get_json(silent=True)
    if (
        request_json
        and "BQ_PROJECT_NAME"
        and "BQ_DATASET_NAME"
        and "BQ_TABLE_NAME"
        and "PDF_INPUT_BUCKET_PATH"
        and "DOCAI_PARSED_JSON_BUCKET_PATH"
        and "CANONICAL_JSON_BUKCET_PATH"
        and "JSONL_BUKCET_PATH"
        and "PROJECT_ID"
        and "DOCAI_LOCATION"
        and "DOCAI_PROCESSOR_ID"
        and "DOCAI_PROCESSOR_VERSION_ID"
    ):
        project_name = request_json["BQ_PROJECT_NAME"]
        dataset_name = request_json["BQ_DATASET_NAME"]
        table_name = request_json["BQ_TABLE_NAME"]
        gs_input_file_path = request_json["PDF_INPUT_BUCKET_PATH"]
        parsed_json_path = request_json["DOCAI_PARSED_JSON_BUCKET_PATH"]
        canonical_json_path = request_json["CANONICAL_JSON_BUKCET_PATH"]
        jsonl_bucket_path = request_json["JSONL_BUKCET_PATH"]
        project_id = request_json["PROJECT_ID"]
        location = request_json["DOCAI_LOCATION"]
        processor_id = request_json["DOCAI_PROCESSOR_ID"]
        processor_version_id = request_json["DOCAI_PROCESSOR_VERSION_ID"]

        # Create or check existence of BigQuery table
        result, schema = create_bigquery(project_name, dataset_name, table_name)
        print(result)

        # Check and insert files into BigQuery
        newly_added_files = check_and_insert_files(
            project_name,
            dataset_name,
            table_name,
            gs_input_file_path,
            parsed_json_path,
            canonical_json_path,
            jsonl_bucket_path,
            project_id,
            location,
            processor_id,
            processor_version_id,
            schema,
        )
        print(f"Newly added files: {newly_added_files}")
        return f"Created table Successfully", 200
    else:
        return "Invalid request", 400
