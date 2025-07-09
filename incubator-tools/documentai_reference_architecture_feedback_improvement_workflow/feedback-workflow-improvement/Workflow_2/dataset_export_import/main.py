"""
Dataset Export and Import
"""

# pylint: disable=W0612
# pylint: disable=E0401
# pylint: disable=R0914
# pylint: disable=W0718
# pylint: disable=W0702
# pylint: disable=R0801

import datetime
import traceback
from google.cloud import storage
from google.cloud import documentai_v1beta3 as documentai
import functions_framework


def delete_blobs_from_prefix(bucket : str, prefix : str) -> None:
    """
    Delete all blobs with the given prefix from the specified bucket.

    Args:
        bucket (str): The name of the Google Cloud Storage bucket.
        prefix (str): The prefix of the blobs to be deleted.

    Returns:
        None
    """
    sc = storage.Client()
    bucket = sc.get_bucket(bucket)
    blobs = bucket.list_blobs(prefix=prefix)
    for blob in blobs:
        try:
            print(f"\tdeleting {blob.name}")
            blob.delete()
        except Exception as e:
            print(e)


def copy_to_feedback_folder(input_bucket : str, input_prefix : str,
                            output_bucket : str, output_prefix : str) -> None:
    """
    Copy blobs from an input bucket and prefix to an output bucket and prefix.

    Args:
        input_bucket (str): The name of the source Google Cloud Storage bucket.
        input_prefix (str): The prefix of the source blobs.
        output_bucket (str): The name of the destination Google Cloud Storage bucket.
        output_prefix (str): The prefix for the destination blobs.

    Returns:
        None
    """
    sc = storage.Client()
    ip_buck_obj = sc.get_bucket(input_bucket)
    out_buck_obj = sc.get_bucket(input_bucket)
    blobs = ip_buck_obj.list_blobs(prefix=input_prefix)
    for blob in blobs:
        old_name = blob.name.split("/")[-1]
        new_name = f"{output_prefix}/{old_name}"
        print(f"\t Copying files to gs://{output_bucket}/{new_name}")
        ip_buck_obj.copy_blob(blob, out_buck_obj, new_name)


def export_dataset(project_id : str, location : str, processor_id : str, gcs_dest_uri : str):
    """
    gcs_dest_uri (str): must start with gs://BUCKET/prefix/to/destination
    """
    gcs_dest_uri = gcs_dest_uri.rstrip("/")
    splits = gcs_dest_uri.split("/")
    output_bucket, output_prefix = splits[2], "/".join(splits[3:])
    sc = storage.Client()
    output_bucket_obj = sc.get_bucket(output_bucket)
    _sc = documentai.DocumentServiceClient()
    dataset_name = f"projects/{project_id}/locations/{location}/processors/{processor_id}/dataset"
    print("Listing all documents in a dataset")
    existing_dataset_documents = _sc.list_documents(
        request=documentai.ListDocumentsRequest(
            dataset=dataset_name
        )
    )
    print("Extracting only Train docs/samples")
    existing_train_dataset = {}
    for document_metadata in existing_dataset_documents.document_metadata:
        if document_metadata.dataset_type.name == "DATASET_SPLIT_TRAIN":
            doc_id = document_metadata.document_id.unmanaged_doc_id.doc_id
            display_name = document_metadata.display_name
            existing_train_dataset[doc_id] = display_name

    print(f"Uploading files to {gcs_dest_uri} for backup...")
    for doc_id, display_name in existing_train_dataset.items():
        unmanaged_doc_id = documentai.DocumentId.UnmanagedDocumentId(doc_id=doc_id)
        get_document_request = documentai.GetDocumentRequest(
            dataset=dataset_name,
            document_id=documentai.DocumentId(unmanaged_doc_id=unmanaged_doc_id)
        )
        res = _sc.get_document(request=get_document_request)
        doc = res.document
        blob_name = f"{output_prefix}/train/{display_name}.json"
        blob = output_bucket_obj.blob(blob_name)
        blob.upload_from_string(documentai.Document.to_json(doc), content_type='application/json')
        print(f"\tExport Done for {display_name}")


def import_dataset(gcs_path_to_import : str, dataset_name : str) -> None:
    """
    Import a dataset into Document AI from Google Cloud Storage.

    Args:
        gcs_path_to_import (str): The Google Cloud Storage path containing the dataset to import.
        dataset_name (str): The name of the dataset in Document AI.

    Returns:
        None
    """
    print(f"Importing Dataset from {gcs_path_to_import} to {dataset_name}")
    _sc = documentai.DocumentServiceClient()
    gcs_prefix = documentai.GcsPrefix(gcs_uri_prefix=gcs_path_to_import)
    input_config = documentai.BatchDocumentsInputConfig(gcs_prefix=gcs_prefix)
    batch_documents_import_configs = documentai.ImportDocumentsRequest.BatchDocumentsImportConfig()
    batch_documents_import_configs.dataset_split = "DATASET_SPLIT_TRAIN"
    batch_documents_import_configs.batch_input_config = input_config
    request = documentai.ImportDocumentsRequest(
        dataset=dataset_name,
        batch_documents_import_configs=[batch_documents_import_configs]
    )
    operation = _sc.import_documents(request=request)

    print("Waiting for operation to complete...")
    try:
        operation.result()
    except Exception as e:
        print(str(e))
    print(operation.metadata)


@functions_framework.http
def dataset_export_import(request):
    """
    Cloud Function to handle the export and import of Document AI datasets.
    """
    try:
        request_json = request.get_json(silent=True)
        if request_json:
            post_hitl_output_uri = request_json.get("post_HITL_output_URI")
            project_id = request_json.get("project_id")
            location = request_json.get("location")
            processor_id = request_json.get("train_processor_id")
            gcs_backup_uri = request_json.get("gcs_backup_uri")
        else:
            post_hitl_output_uri = request.args.get("post_HITL_output_URI")
            project_id = request.args.get("project_id")
            location = request.args.get("location")
            processor_id = request.args.get("train_processor_id")
            gcs_backup_uri = request.args.get("gcs_backup_uri")

        try:

            post_hitl_output_uri = post_hitl_output_uri.rstrip("/")

            # Backing up existing dataset before training new processor
            now = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            gcs_backup_uri = f'{gcs_backup_uri.rstrip("/")}/{now}'
            print(f"Exporting Dataset from {processor_id} to {gcs_backup_uri}")
            export_dataset(project_id, location, processor_id, gcs_backup_uri)

            # Import dataset from post_HITL_output_URI folder
            dataset_name = f"""projects/{project_id}/locations/{location}/processors/
                            {processor_id}/dataset"""
            import_dataset(post_hitl_output_uri, dataset_name)

            return {"state": "SUCCESS", "message": f"""Dataset exported to {gcs_backup_uri}
            and data from {post_hitl_output_uri} imported to processor {processor_id}"""}, 200

        except Exception as e:
            print(e)
            return {"state" : "FAILED", "message" : f"""UNABLE TO COMPLETE BECAUSE OF {e},
            {traceback.format_exc()}", "backup_uri" : f"{gcs_backup_uri}"""}, 500

    except Exception as e:
        print(e)
        return {"state" : "FAILED", "message" : """UNABLE TO GET THE NEEDED
                PARAMETERS TO RUN THE CLOUD FUNCTION"""}, 400
