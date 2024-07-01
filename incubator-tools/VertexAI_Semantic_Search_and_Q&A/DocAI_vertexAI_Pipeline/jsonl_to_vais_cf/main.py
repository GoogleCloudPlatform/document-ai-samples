import functions_framework
from google.cloud import discoveryengine_v1 as vs
from google.cloud import storage
import ndjson


# Triggered by a change in a storage bucket
@functions_framework.cloud_event
def jsonl_vais(cloud_event):
    data = cloud_event.data
    event_id = cloud_event["id"]
    event_type = cloud_event["type"]

    bucket = data["bucket"]
    name = data["name"]
    metageneration = data["metageneration"]
    timeCreated = data["timeCreated"]
    updated = data["updated"]
    print(
        f"Event ID: {event_id} -- Event type: {event_type} --  Metageneration: {metageneration} --  Created: {timeCreated}  -- Updated: {updated}"
    )
    print(f"Bucket: {bucket} -- File: {name}")

    client = vs.DocumentServiceClient()
    request = vs.ImportDocumentsRequest(
        parent="projects/514064100333/locations/global/collections/default_collection/dataStores/pdf-json_1699996276496/branches/0",
        gcs_source=vs.GcsSource(
            input_uris=[f"gs://{bucket}/{name}"], data_schema="document"
        ),
        reconciliation_mode=vs.ImportDocumentsRequest.ReconciliationMode.INCREMENTAL,
    )
    operation = client.import_documents(request=request)
    print(f"Waiting for operation to complete: {operation.operation.name}")
    response = operation.result()
    metadata = vs.ImportDocumentsMetadata(operation.metadata)
    print(response)
    print(metadata)
    client = storage.Client()  # Create a GCS client
    bucket = client.get_bucket(bucket)  # Get the GCS bucket
    blob = bucket.blob(name)  # Create a new blob in the bucket
    blob.content_type = "application/json"
    bucket2 = client.get_bucket("venky_canonical_jsons_bucket")
    success_blob = bucket2.blob(f"vais_status/success/{name}")
    failed_blob = bucket2.blob(f"vais_status/failed/{name}")

    if response.error_samples:
        try:
            jsonl = blob.download_as_string()

            success = []
            failed = []
            li = []
            source = ndjson.loads(jsonl)
            for i in response.error_samples:
                li.append(int(i.details[0].value.decode("utf-8").split(":")[-1]))
            # print("Done")
            for i in range(0, len(source)):
                if i + 1 in li:
                    failed.append(source[i])
                else:
                    success.append(source[i])
            success_blob.upload_from_string(
                ndjson.dumps(success), content_type="application/json"
            )
            failed_blob.upload_from_string(
                ndjson.dumps(failed), content_type="application/json"
            )
            print(
                "Partially imported and deleted the Blob after moving success and failed folders: ",
                blob,
                "******",
                blob.delete(),
            )
        except Exception as e:
            print("Error : ", e)
    else:
        bucket.copy_blob(
            blob=blob, destination_bucket=bucket2, new_name=success_blob.name
        )
        print(
            "Imported Successfully and deleted the Blob: ",
            blob,
            "******",
            blob.delete(),
        )
