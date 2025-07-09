"""
Exporting HITL Reviewed Documents
"""

# pylint: disable=E0401
# pylint: disable=R0914
# pylint: disable=W0718
# pylint: disable=W0702
# pylint: disable=R0801

import traceback
from google.cloud import storage
from google.cloud import documentai_v1beta3 as documentai
import functions_framework


# 1. delete files in after human_review folder before exporting dataset
def delete_blobs_from_prefix(bucket : str, prefix : str) -> None:
    """
    Delete files in after human_review folder before exporting dataset
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


# 2. Export Dataset to after human review folder
def export_dataset(project_id : str, location : str, processor_id : str,
                   gcs_dest_uri : str) -> None:
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
    existing_train_dataset = {}
    for existing_dataset_document in existing_dataset_documents:
        if existing_dataset_document.dataset_type.name == "DATASET_SPLIT_TRAIN":
            # print(existing_dataset_document.dataset_type.name)
            doc_id = existing_dataset_document.document_id.unmanaged_doc_id.doc_id
            display_name = existing_dataset_document.display_name
            existing_train_dataset[doc_id] = display_name

    print(f"Uploading files to {gcs_dest_uri}")
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


@functions_framework.http
def export_hitl_reviewed_docs(request):
    """
    Cloud Function to handle the export and review HITL documents.
    """
    try:
        request_json = request.get_json(silent=True)
        if request_json:
            project_id = request_json.get("project_id")
            location = request_json.get("location")
            processor_id = request_json.get("hitl_processor_id")
            post_hitl_output_uri = request_json.get("post_HITL_output_URI")
        else:
            project_id = request.args.get("project_id")
            location = request.args.get("location")
            processor_id = request.args.get("hitl_processor_id")
            post_hitl_output_uri = request.args.get("post_HITL_output_URI")

        try:
            post_hitl_output_uri = post_hitl_output_uri.rstrip("/")

            splits = post_hitl_output_uri.split("/")
            output_bucket, output_prefix = splits[2], "/".join(splits[3:])

            print(f"Deleting existing files from {post_hitl_output_uri}")
            delete_blobs_from_prefix(output_bucket, output_prefix)

            print(f"Exporting Dataset from Processor: {processor_id} to {post_hitl_output_uri}")
            export_dataset(project_id, location, processor_id, post_hitl_output_uri)

            return {"state" : "SUCCESS", "message" : f"""Dataset exported from
                    Processor : {processor_id} to {post_hitl_output_uri}"""}, 200

        except Exception as e:
            print(e)
            return {"state" : "FAILED", "message" : f"""UNABLE TO COMPLETE BECAUSE OF {e},
                    {traceback.format_exc()}"""}, 500

    except Exception as e:
        print(e)
        return {"state" : "FAILED", "message" : """UNABLE TO GET THE NEEDED PARAMETERS
                                            TO RUN THE CLOUD FUNCTION"""}, 400
