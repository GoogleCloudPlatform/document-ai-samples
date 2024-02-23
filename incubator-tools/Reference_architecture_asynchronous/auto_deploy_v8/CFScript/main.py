import concurrent.futures
from typing import List

import pandas as pd
from google.cloud import documentai, firestore, storage
from utilities import batch_process_documents_sample, copy_blob, list_blobs

"""
project_name          = 'xx-xx-xx'
input_bucket_name     = 'xx-db-test'  #'xx_shell_input'
project_id            = 'xxxxxx'
location              = 'us'
processor_id          = 'xxx6fxxec5xx'
gcs_output_uri_prefix = 'daira_outputs'
"""

input_bucket_name = "daira_test_zaid_5"
gcs_output_uri_prefix = "daira_outputs"

# read the config data
storage_client = storage.Client()
bucket = storage_client.bucket(input_bucket_name)
blob = bucket.blob("config/config.txt")  # gs://daira-db-test/config/config.txt
config_data = blob.download_as_string().decode("utf-8")

print(str(config_data).split("\n"))

input_parameters = str(config_data).split("\n")
project_name = input_parameters[0].split(":")[1].strip()
location = input_parameters[2].split(":")[1].strip()
processor_id = input_parameters[6].split("/")[-1]
project_id = input_parameters[6].split("/")[1]

print("input_bucket_name ", input_bucket_name)
print("project_name ", project_name)
print("location ", location)
print("processor_id ", processor_id)
print("project_id ", project_id)

metadata_array = []

connection = firestore.Client(project=project_name)


def delete_blob(bucket_name: str, blob_name: str) -> None:
    """
    Deletes specified blob name from Google Cloud Storage bucket .

    Args:
        bucket_name (str): The name of the bucket.
        blob_name (str):  The name of the blob inside the bucket.

    Returns:
        None. If the blob exists, it will be deleted the blob.
        If it doesn't exist or an error occurs,
        the function will silently pass.
    """
    print("delete_blob")
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    try:
        blob.delete()
    except BaseException:
        pass


def bucket_cleaner(bucket_name: str) -> None:
    """
    Deletes all the blob inside the Google Cloud Storage bucket .

    Args:
        bucket_name (str): The name of the bucket from where the blobs need to be deleted.
    """
    print("bucket_cleaner")
    bucket_blobs_list = list_blobs(bucket_name)
    for i in bucket_blobs_list:
        delete_blob(bucket_name, i)


def db_insert(info_list_holder: List) -> None:
    """
    Function to write the logs in the database having file_name as the primary key.

    Args:
        info_list_holder (List): The list of all the details related to the documents which
        contains metadata of the file, operation id, file storage location.
    """
    print("db_insert")
    global connection
    for i in info_list_holder:
        for j in i:
            file_name = j["filename"]
            doc_reference = connection.collection("daira_logs").document(file_name)
            doc_reference.set(j)


def db_print() -> pd.DataFrame:
    """
    Function to get all the logs stored in database name 'daira_logs' and store it in a dataframe.

    Return (pd.DataFrame):

            It returns the dataframe having all the logs from the database.
    """
    print("db_print")
    global connection
    db_entries = []
    reference = connection.collection("daira_logs")
    docs = reference.stream()
    for doc in docs:
        db_entries.append(doc.to_dict())
    db_dataframe = pd.DataFrame(db_entries)
    return db_dataframe


def bucket_lister(bucket_name: str) -> List:
    """
    Collects all the file name and create the GCS bucket path of the file in the given bucket name.

    Args:
        bucket_name (str): The name of the bucket from where the blobs need to be discovered.

    Returns (List):
        The list having the full GCS path of thr file inside the bucket name provided by the user.
    """

    print("bucket_lister")
    storage_client = storage.Client()
    blobs = storage_client.list_blobs(bucket_name)
    blob_arr = []
    for blob in blobs:
        blob_arr.append("gs://" + bucket_name + "/" + blob.name)
    return blob_arr


def create_bucket_class_location(bucket_name: str) -> str:
    """
    It will create a specified Google Cloud Storage bucket with the US region .

    Args:
        bucket_name (str): The name of the bucket to create.

    Returns:
        str:
        The bucket name as string form.
    """
    print("create_bucket_class_location")
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    print("Bucket Created successfully : ", bucket)
    return bucket


def batch_caller(gcs_input_uri, gcs_output_uri):
    """It will perform Batch Process by calling the batch_process_documents_sample function.

    Args:
        gcs_input_uri (str): GCS path which contains all input files
        gcs_output_uri (str): GCS path to store processed JSON results
    """

    print("batch_caller:")
    print(gcs_input_uri, gcs_output_uri)
    global project_id
    global location
    global processor_id
    global gcs_output_uri_prefix
    global metadata_array
    print("BATCH_CALLER project_id : ", project_id)
    operation = batch_process_documents_sample(
        project_id,
        location,
        processor_id,
        gcs_input_uri,
        f"{gcs_output_uri}/{gcs_output_uri_prefix}/",
    )
    metadata = documentai.BatchProcessMetadata(operation.metadata)
    metadata_array.append(metadata)


def metadata_reader(metadata: documentai.BatchProcessMetadata) -> List:
    """It will read the metadata details from the batch processsed and store it in an array.

    Args:
        metadata (str): GCS path which contains all input files

    Return:
        List:
        Returns list with all the required metadata of the files.
    """
    print("metadata_reader")
    info_array = []
    metadata_ips = metadata.individual_process_statuses
    metadata_state = metadata.state.name
    metadata_createtime = metadata.create_time.ctime()
    metadata_updatetime = metadata.update_time.ctime()
    for i in metadata_ips:
        info_array.append(
            {
                "filename": i.input_gcs_source.split("/")[-1],
                "metadata_state": metadata_state,
                "metadata_createtime": metadata_createtime,
                "metadata_updatetime": metadata_updatetime,
                "operation_id": i.output_gcs_destination.split("/")[-2],
                "file_output_gcs_destination": i.output_gcs_destination,
                "file_human_review_status": i.human_review_status.state.name,
                "file_human_review_operation_id": i.human_review_status.human_review_operation.split(
                    "/"
                )[
                    -1
                ],
            }
        )
    return info_array


def file_copy(array_having_file_names: List, bucket_name_with_folder: str) -> None:
    """
    Copies a blob (file/object) from one GCP storage bucket to another.

    Args:
        array_having_file_names (List) : List of file names
        blob_name (str): Name of the blob (file/object) in the source bucket to be copied.
        destination_bucket_name (str): Name of the destination bucket.
        destination_blob_name (str): Desired name for the blob in the destination bucket.

    Output:
        None. The blob is copied to the destination bucket with the specified name.
    """
    print("file_copy")
    for i in array_having_file_names:
        bucket_name = i.split("/")[-2]
        blob_name = i.split("/")[-1]
        destination_bucket_name = bucket_name_with_folder.split("/")[2]
        temp = bucket_name_with_folder.split("/")[3:]
        destination_blob_name = "/".join(temp) + blob_name
        print(
            "-- copy_blob --> ",
            bucket_name,
            "|",
            blob_name,
            "|",
            destination_bucket_name,
            "|",
            destination_blob_name,
        )
        copy_blob(
            bucket_name, blob_name, destination_bucket_name, destination_blob_name
        )


def concurrentProcessing(
    batch_caller, daira_output_test: str, batch_array: List
) -> None:
    """
    To create a concurrent process for batch processing the files .

    Args:
        batch_caller (Function) : Function which will call the batch processing
        daira_output_test (str): A temporary bucket name where all the batch processed file get stored.
        batch_array (List): List of all the copied files from temporary bucket which needs to processed.

    """
    print("--concurrentProcessing--")
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        print("processing completed", executor)


def hello_world(request) -> str:
    """
    HTTP Cloud Function which will get deployed and run by the cloud scheduler every hour.
    For more information on how to deploy cloud function
    https://cloud.google.com/functions/docs/create-deploy-gcloud-1st-gen.
    Args:
        request : urllib.request: The request object.

    Return:
        str:
        Returns the success message.

    """
    print("--STARTED--")

    # delete previous ran diara-logs in firestore - if u r testing for same
    # files
    try:
        previously_done_files = list(db_print()["filename"])
        print("previously_done_files : ", previously_done_files)
    except BaseException:
        previously_done_files = []

    input_bucket_files_list = bucket_lister(input_bucket_name)

    # pop the element (config file) from the input bucket file
    input_bucket_files_list.remove("gs://" + input_bucket_name + "/config/config.txt")

    files_to_process = [
        i
        for i in input_bucket_files_list
        if i.split("/")[-1] not in previously_done_files
    ]
    print("files_to_process : ", files_to_process)
    start = 0
    end = len(files_to_process)
    step = 50

    process_batch_array = []
    for i in range(start, end, step):
        x = i
        process_batch_array.append(files_to_process[x : x + step])
    print("process_batch_array : ", process_batch_array)

    # test vars
    diara_processing_test = "daira-processing-test02"
    daira_output_test = "daira-output-test02"

    try:
        print("creating : daira-processing-test")
        create_bucket_class_location(diara_processing_test)  # 'daira-processing-test03'
        print("creating : daira-output-test")
        create_bucket_class_location(daira_output_test)  # 'daira-output-test03'
    except Exception as exc:
        print("Bucket exists!")
        print(exc)

    bucket_cleaner(diara_processing_test)  # 'daira-processing-test03'
    lenght = len(process_batch_array)
    print(process_batch_array)

    for i in range(0, len(process_batch_array)):
        array_having_file_names = process_batch_array[i]
        bucket_name_with_folder = (
            "gs://" + diara_processing_test + "/batches/" + str(i) + "/"
        )
        print(i, " | ", process_batch_array[i], " | ", bucket_name_with_folder)
        file_copy(array_having_file_names, bucket_name_with_folder)

    batch_array = [
        "gs://" + diara_processing_test + "/batches/" + str(i) + "/"
        for i in range(lenght)
    ]
    print(batch_array)

    concurrentProcessing(batch_caller, daira_output_test, batch_array)

    print("metadata_array:")
    print(metadata_array)

    info_list_holder = [metadata_reader(i) for i in metadata_array]
    db_insert(info_list_holder)
    print(info_list_holder)
    print("--ENDED--")
    return "Diara Done!"
