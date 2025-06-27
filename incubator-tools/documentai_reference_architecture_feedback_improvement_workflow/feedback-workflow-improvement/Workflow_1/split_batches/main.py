"""
Splitting the files into several batches
"""
# pylint: disable=E0401
# pylint: disable=R0914
# pylint: disable=W0718
# pylint: disable=W0613
# pylint: disable=W0702


from io import StringIO
import concurrent.futures
import functions_framework
from google.cloud import storage
import pandas as pd

def delete_gcs_folder(gcs_temp_path_delete):
    """
    Deletes all files inside a specific folder in a GCS bucket and the folder itself.
    
    :param gcs_folder_path.
    """
    # Initialize the GCS client
    bucket_name=gcs_temp_path_delete.split('/')[2]
    folder_path=('/').join(gcs_temp_path_delete.split('/')[3:])
    client = storage.Client()

    # Get the bucket
    bucket = client.get_bucket(bucket_name)

    # Add trailing slash to the folder path if not present
    if not folder_path.endswith('/'):
        folder_path += '/'

    # List all blobs (files) in the folder
    blobs = bucket.list_blobs(prefix=folder_path)

    # Delete all the blobs (files)
    for blob in blobs:
        # print(f"Deleting {blob.name}")
        blob.delete()

    # print(f"Deleted all files in {folder_path}")

def process_files(project_id,df, gcs_temp_path, gcs_input_path, batch_size=30):
    """
    Process files by copying them from the input path to temporary batches in GCS.

    Args:
        project_id (str): The Google Cloud project ID.
        df (pandas.DataFrame): DataFrame containing file information.
        gcs_temp_path (str): GCS path for temporary storage.
        gcs_input_path (str): GCS path for input files.
        batch_size (int, optional): Number of files per batch. Defaults to 30.

    Returns:
        None

    This function splits the input files into batches and copies them to temporary
    folders in Google Cloud Storage for batch processing.
    """
    storage_client = storage.Client()
    # Configuration
    gcs_temp_bucket_name = gcs_temp_path.split('/')[2]
    gcs_temp_folder_path = ('/').join(gcs_temp_path.split('/')[3:])
    origin_bucket_name = gcs_input_path.split('/')[2]

    # Step 1: Getting files where Batch_processed = "No"
    # filtered_df = df[df['Batch_processed'] == 'No'][['File_name', 'GCS_folder_path']]

    try:
        delete_gcs_folder(gcs_temp_path)
    except:
        pass
    # Step 2: Split the files into batches of `batch_size`
    files = [{"File_name": row["File_name"],
              "GCS_folder_path": row["GCS_folder_path"]} for index, row in df.iterrows()]
    file_batches = [files[i:i + batch_size] for i in range(0, len(files), batch_size)]
    # print(file_batches)
    # Step 3: Function to copy files and create temporary GCS folder
    def create_temp_folder_and_copy(batch, batch_number):
        temp_folder_path = f"{gcs_temp_folder_path}temp_batch_{batch_number}/"
        temp_bucket = storage_client.bucket(gcs_temp_bucket_name)
        origin_bucket = storage_client.bucket(origin_bucket_name)

        for file_info in batch:
            if not file_info['GCS_folder_path'].endswith('/'):
                file_info['GCS_folder_path'] += '/'
            # Ensure the GCS folder path does not contain 'gs://'
            source_blob_name = file_info['GCS_folder_path'].replace(
                f"gs://{origin_bucket_name}/", "") + file_info['File_name']
            destination_blob_name = f"{temp_folder_path}{file_info['File_name']}"
            print(source_blob_name)

            # Copy the file to the temporary folder
            source_blob = origin_bucket.blob(source_blob_name)
            destination_blob = temp_bucket.blob(destination_blob_name)
            destination_blob.rewrite(source_blob)
            print(f"Copied {file_info['File_name']} to {temp_folder_path}")

    # Step 4: Concurrent processing with ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(
            create_temp_folder_and_copy,
            batch, idx + 1) for idx, batch in enumerate(file_batches)]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()  # Wait for each task to complete
            except Exception as e:
                print(f"An error occurred: {e}")

@functions_framework.http
def split_copy_files(request):
    """
    Cloud Function to handle the process of splitting and copying files.

    Returns:
        tuple: A tuple containing a dictionary with process results and an HTTP status code.
            The dictionary includes:
            - 'dataframe': JSON representation of the processed DataFrame
            - 'state': Status of the operation ('DONE' or 'FAILED')
            - 'message': Descriptive message about the operation result

    This function extracts parameters from the request, calls the process_files
    function to split and copy files, and returns the result of the operation.
    """
    # Extract parameters from the request body (if POST) or query parameters (if GET)
    try:
        request_json = request.get_json(silent=True)
        print(request_json)
        # df=pd.read_json(StringIO(x['dataframe']), orient='records')
        if request_json:
            project_id = request_json.get("project_id")
            gcs_temp_path = request_json.get("gcs_temp_path")
            gcs_input_path = request_json.get("gcs_input_path")
            batch_size = request_json.get("batch_size")
            df=pd.read_json(StringIO(request_json.get('dataframe')), orient='records')
        else:
            project_id = request.args.get("project_id")
            gcs_temp_path = request.args.get("gcs_temp_path")
            gcs_input_path = request.args.get("gcs_input_path")
            batch_size = request.args.get("batch_size")
            df=pd.read_json(StringIO(request.args.get('dataframe')), orient='records')
        print(df)
        # Call the function
        try:
            process_files(project_id,df, gcs_temp_path, gcs_input_path, batch_size)

            return {'dataframe':df.to_json(orient="records"),"state":"DONE",
                    "message":"""Files are split into batches and moved
                    to temporary folders for bacth processing"""}, 200
        except Exception as e:
            print(e)
            return {"state":"FAILED","message":f"UNABLE TO copy files because of {e}"}, 500
    except Exception as e:
        print(e)
        return {"state":"FAILED","message":f"""UNABLE TO GET THE NEEDED PARAMETERS
        TO RUN THE CLOUD FUNCTION BECAUSE OF {e}"""}, 400
