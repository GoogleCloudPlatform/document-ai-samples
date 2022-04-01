from google.cloud import bigquery
from google.cloud import documentai_v1 as documentai
from google.cloud import storage

# Read environment variables
project_id = os.environ.get("GCP_PROJECT")
location = os.environ.get("PARSER_LOCATION")
processor_id = os.environ.get("PROCESSOR_ID")
timeout = int(os.environ.get("TIMEOUT"))
dataset_name = os.environ.get("BQ_DATASET_NAME")
table_name = os.environ.get("BQ_TABLE_NAME")

# Set variables
gcs_output_uri = f"gs://{project_id}-output-receipts"
gcs_archive_bucket_name = f"{project_id}-archived-receipts"
gcs_rejected_bucket_name = f"{project_id}-rejected-files"
processor = f"projects/{project_id}/locations/{location}/processors/{processor_id}"
accepted_file_types = [
    "application/pdf",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/tiff",
    "image/jpeg",
    "image/tif",
    "image/webp",
    "image/bmp",
]

# Create GCP clients
docai_client = documentai.DocumentProcessorServiceClient()
storage_client = storage.Client()
bq_client = bigquery.Client()

# entry point for Cloud Functions
def process_receipt(event, context):
    input_bucket_name = event["bucket"]
    file_name = event["name"]
    content_type = event["contentType"]

    if content_type in accepted_file_types:
        file = get_gcs_file(file_name, input_bucket_name)
        extracted_doc = extract_entities(file, content_type)
        extracted_list = format_entities(extracted_doc)
        write_to_bq(dataset_name, table_name, extracted_list, file_name)
        # Copy input file to archive bucket
        copy_blob(input_bucket_name, gcs_archive_bucket_name, file_name)
    else:
        print("Cannot parse the file type.")
        # move file to designated bucket if file type is not supported
        copy_blob(input_bucket_name, gcs_rejected_bucket_name, file_name)
    return


# write data to a BigQuery table
def write_to_bq(dataset_name, table_name, extracted_list, file_name):
    dataset_ref = bq_client.dataset(dataset_name)
    table_ref = dataset_ref.table(table_name)

    for item in extracted_list:
        item["doc_name"] = file_name

    json_data = json.dumps(extracted_list, sort_keys=False)

    # Convert to a JSON Object
    json_object = json.loads(json_data)

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        ignore_unknown_values=True,
        schema=[
            bigquery.SchemaField("doc_name", "STRING"),
            bigquery.SchemaField("confidence", "FLOAT"),
            bigquery.SchemaField("type_", "STRING"),
            bigquery.SchemaField("mention_text", "STRING"),
        ],
    )

    job = bq_client.load_table_from_json(json_object, table_ref, job_config=job_config)
    error = job.result()  # Waits for table load to complete.


def get_gcs_file(file_name, bucket_name):
    bucket = storage_client.get_bucket(bucket_name)
    gcs_file = bucket.get_blob(file_name)
    file_blob = gcs_file.download_as_bytes()
    return file_blob


def extract_entities(file, content_type):
    document = {"content": file, "mime_type": content_type}

    request = {"name": processor, "raw_document": document, "skip_human_review": True}

    results = docai_client.process_document(request)

    print("Entities extracted from DocAI.")
    return results.document


# Format all entities into a list to write into a BQ table
def format_entities(extracted_doc):
    result_ents = []

    for entity in extracted_doc.entities:
        entity_type = str(entity.type_)
        if entity_type == "line_item":
            for property in entity.properties:
                ents = {
                    "type_": property.type_,
                    "mention_text": property.mention_text,
                    "confidence": property.confidence,
                }
                result_ents.append(ents)
            ents = {
                "type_": entity.type_,
                "mention_text": entity.mention_text,
                "confidence": entity.confidence,
            }
            result_ents.append(ents)
        else:
            ents = {
                "type_": entity_type,
                "mention_text": entity.mention_text,
                "confidence": entity.confidence,
            }
            result_ents.append(ents)

    print("Formatted entities to a list.")
    return result_ents


# copy a blob from one bucket to another by name
def copy_blob(source_bucket_name, dest_bucket_name, blob_name):
    source_bucket = storage_client.get_bucket(source_bucket_name)
    dest_bucket = storage_client.get_bucket(dest_bucket_name)
    blob = source_bucket.get_blob(blob_name)

    source_bucket.copy_blob(blob, dest_bucket, blob_name)
    blob.delete()
    return
