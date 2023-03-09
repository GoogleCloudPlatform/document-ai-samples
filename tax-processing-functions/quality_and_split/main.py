"""Copyright 2023 Google LLC

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

     https://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""

# THIS IS JUST DEMO CODE

from datetime import datetime
import json
import os

from google.cloud import bigquery
from google.cloud import documentai
from google.cloud import exceptions
from google.cloud import pubsub_v1
from google.cloud import storage
import ndjson

# Set Debug True/False
DEBUG = False

# Read GCS environment variables
project_id = os.environ.get("GCP_PROJECT")
project_name = os.environ.get("GCP_PROJECT_NAME")
location = os.environ.get("PARSER_LOCATION")
bucket_1040c_input = os.environ.get("BUCKET_1040C_INPUT")
bucket_1120s_input = os.environ.get("BUCKET_1120S_INPUT")
bucket_1040c_processed = os.environ.get("BUCKET_1040C_PROCESSED")
bucket_1120s_processed = os.environ.get("BUCKET_1120S_PROCESSED")
bucket_rejected = os.environ.get("BUCKET_REJECTED")
input_bucket_name = os.environ.get("INPUT_BUCKET")
file_name = os.environ.get("FILE_NAME")
content_type = os.environ.get("CONTENT_TYPE")

# BQ variables
dataset_name = os.environ.get("BQ_DATASET_NAME")
table_name = os.environ.get("BQ_TABLE_NAME")

# Pub/Sub variables
uil_review_topic_name = os.environ.get("PUBSUB_UIL_REVIEW_TOPIC_NAME")
workflow_topic_name = os.environ.get("PUBSUB_WORKFLOW_TOPIC_NAME")

# Set Document AI processor variables
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
processor_quality = (
    f"projects/{project_id}/locations/us/processors/{os.environ.get('PROCESSOR_ID_Q')}"
)
processor_classification = f"projects/{project_id}/locations/us/processors/{os.environ.get('PROCESSOR_ID_CLASS')}"
processor_1040 = f"projects/{project_id}/locations/us/processors/{os.environ.get('PROCESSOR_ID_1040')}"
processor_1120 = f"projects/{project_id}/locations/us/processors/{os.environ.get('PROCESSOR_ID_1120')}"

# Create GCP clients
docai_client = documentai.DocumentProcessorServiceClient()
storage_client = storage.Client()
bq_client = bigquery.Client()
publisher = pubsub_v1.PublisherClient()
ts_format = "%Y-%m-%d_%H:%M:%S"


# Entry point for Cloud Function
def process_receipt(event, context):
    # event = cloud function event
    # global input_bucket_name
    # global file_name
    # global content_type
    input_bucket_name = event["bucket"]
    file_name = event["name"]
    content_type = event["contentType"]  # TODO: rewrite
    print(f"Found content type:{content_type}")

    if content_type in accepted_file_types:
        # Gets file blob
        file = get_gcs_file(file_name, input_bucket_name)

        # Extracts entities from Document AI
        extracted_doc = extract_entities(file, content_type, processor_quality)

        # Splitter--function, parse quality metrics
        avg_q = parse_quality_metrics(extracted_doc)  # IDQ JSON Output (Quality)

        # Separate documents by quality threshold
        if avg_q > 0.05:
            # Extract document entities using classification processor
            extracted_classifier_doc = extract_entities(
                file, content_type, processor_classification
            )

            if DEBUG:
                print(extracted_classifier_doc)  # Splitter/classifier JSON output

            # Parse documents
            parse_doc_type(
                extracted_classifier_doc,
                file,
                file_name,
                content_type,
                workflow_topic_name,
                input_bucket_name,
            )

        else:
            print("Fail, image qualtity is bad")
            # Extract entities and push to pubsub for review
            extracted_classifier_doc = extract_entities(
                file, content_type, processor_classification
            )
            extracted_noid_doc_processed = format_entities(extracted_classifier_doc)
            json_string = json.dumps(extracted_noid_doc_processed, sort_keys=False)
            topic_path = publisher.topic_path(project_id, uil_review_topic_name)
            publish_to_pubsub(topic_path, json_string)

    else:
        print(f"Cannot parse the file type. Acceoted types are {accepted_file_types}")
        # Move file to rejected GCS bucket
        move_blob(input_bucket_name, bucket_rejected, blob_name=file_name)
        return


# Splitter function - return the average quality rating for document entities
# DISCLAIMER: this returns an average quality of entities in the document
def parse_quality_metrics(raw_content):
    # raw_content = entities extracted from DocAI processor
    if raw_content:
        num_pages = len(raw_content.entities)
        total = 0
        for entity in raw_content.entities:
            if str(entity.type_) == "quality_score":
                total += entity.confidence
        avg_q = total / num_pages
        print(f"Average quality in document entities: {avg_q}")
        return avg_q


# Parse document by type and upload to respective GCS, BQ, and Pub/Sub objects
def parse_doc_type(
    raw_content, file, file_name, content_type, topic_name, input_bucket_name
):
    # raw_content = raw entities extracted from Document AI processor
    # file = GCS blob file object
    # file_name = "local/path/to/file"
    # content_type = type of event file uploaded
    # topic_name = topic to push processed file to
    # input_bucket_name = GCS bucket to copy final processed doc to
    if raw_content:
        for entity in raw_content.entities:
            if "1040sc" in str(entity.type):
                # move to 1040c input bucket
                move_blob(input_bucket_name, bucket_1040c_input, blob_name=file_name)

                # extract and format entities from document
                extracted_1040_doc = extract_entities(
                    file, content_type, processor_1040
                )  # parse 1040c doc
                extracted_1040_doc_processed = format_entities(
                    extracted_1040_doc
                )  # formatted
                json_string = json.dumps(extracted_1040_doc_processed, sort_keys=False)

                # Get timestamp and upload to GCS
                stamp = datetime.now()
                str_date_time = stamp.strftime(ts_format)
                upload_blob(
                    bucket_1040c_processed,
                    f"1040sc_{str_date_time}_{file_name}",
                    json_string,
                )

                # Write formatted data to BQ Table
                write_to_bq(
                    project_name,
                    dataset_name,
                    table_name,
                    extracted_1040_doc_processed,
                    file_name,
                    "1040sc",
                )
                print("1040sc output has been written to BQ.")

                # Publish to pubsub
                topic_path = publisher.topic_path(project_id, topic_name)
                publish_to_pubsub(topic_path, json_string)

            elif "1120s" in str(entity.type):
                # move to 1040c input bucket
                move_blob(input_bucket_name, bucket_1120s_input, blob_name=file_name)

                # extract and format entities from document
                extracted_1120_doc = extract_entities(
                    file, content_type, processor_1120
                )  # parse 1120s doc
                extracted_1120_doc_processed = format_entities(
                    extracted_1120_doc
                )  # formatted
                json_string = json.dumps(extracted_1120_doc_processed, sort_keys=False)

                # Get timestamp and upload to GCS
                stamp = datetime.now()
                str_date_time = stamp.strftime(ts_format)
                upload_blob(
                    bucket_1120s_processed,
                    f"1120sk_{str_date_time}_{file_name}",
                    json_string,
                )

                # Write formatted data to BQ Table
                write_to_bq(
                    project_name,
                    dataset_name,
                    table_name,
                    extracted_1120_doc_processed,
                    file_name,
                    "1120ssk1",
                )
                print("1120s output has been written to BQ.")

                # Publish to pubsub
                topic_path = publisher.topic_path(project_id, topic_name)
                publish_to_pubsub(topic_path, json_string)

            # TODO: Add handling for type other if needed
    return


# Format extracted JSON output to a list
def format_entities(extracted_doc):
    # extracted_doc = results from DocAI processor
    result_ents = []
    for entity in extracted_doc.entities:
        entity_type = str(entity.type_)
        for p in entity.properties:
            ents = {
                "type_": p.type_,
                "mention_text": p.mention_text,
                "confidence": p.confidence,
            }

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


# Write processed JSON results to BigQuery table
def write_to_bq(
    project_name, dataset_name, table_name, extracted_list, file_name, type
):
    # project_name = string, Google Cloud Project name
    # dataset_name = string, BQ dataset name to import to
    # table_name = string, BQ table name to import to
    # extracted_list = data in JSON list format
    # file_name = document name
    # type = document type
    table_ref = bigquery.dataset.DatasetReference(project_name, dataset_name).table(
        table_name
    )
    date_loaded = datetime.now().strftime(
        ts_format
    )  # Create timestamp processed_date in string format

    for item in extracted_list:
        item["doc_name"] = file_name
        item["doc_type"] = type
        item["processed_date"] = date_loaded

    json_data = json.dumps(extracted_list, sort_keys=False)

    # Convert to a JSON Object
    json_object = json.loads(json_data)

    # BQ Schema
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        ignore_unknown_values=True,
        write_disposition="WRITE_APPEND",
        schema=[
            bigquery.SchemaField("processed_date", "STRING"),
            bigquery.SchemaField("doc_name", "STRING"),
            bigquery.SchemaField("doc_type", "STRING"),
            bigquery.SchemaField("confidence", "FLOAT"),
            bigquery.SchemaField("type_", "STRING"),
            bigquery.SchemaField("mention_text", "STRING"),
        ],
    )
    job = bq_client.load_table_from_json(json_object, table_ref, job_config=job_config)
    print(f"BQ upload job results:{job.result()}")


# Upload files to GCP Bucket
def upload_blob(bucket_name, file_name, json_string):
    # bucket_name = "your-bucket-destination-name" in GCS
    # file_name = intended file name "local/path/to/file/destination"
    # json_string = data to be moved to GCS bucket in json string format
    nd_output = ndjson.dumps(json.loads(json_string))
    bucket = storage_client.bucket(bucket_name)
    bucket.blob(file_name).upload_from_string(nd_output)
    print(f"File {file_name} uploaded to {file_name}.")


# Get Google Cloud Storage file blob
def get_gcs_file(file_name, bucket_name):
    # file_name = string, name of Google Cloud Storage file
    # bucket_name = string, name of Google Cloud Storage bucket
    try:
        input_bucket = storage_client.get_bucket(bucket_name)
        gcs_file = input_bucket.get_blob(file_name)
        file_blob = gcs_file.download_as_bytes()
        print(f"File {file_name} blob extracted from {bucket_name}.")
        return file_blob

    except exceptions.Forbidden as e:
        print(f"File {file_name} not in {bucket_name}. Error: {e}")
        raise

    except exceptions.BadRequest:
        print("Bad request: Check file and bucket name")
        raise

    except Exception as e:
        print(
            f"File {file_name} blob extracted from {bucket_name} failed, due to {e} error"
        )
        raise


# Extract entites from document using respective processor
def extract_entities(file, content_type, processor):
    # file = file object
    # content_type = type of file uploaded
    # processor = int, DocAI processor ID
    raw_document = documentai.RawDocument(content=file, mime_type=content_type)
    request = documentai.ProcessRequest(name=processor, raw_document=raw_document)
    result = docai_client.process_document(request=request)
    print(f"Entities extracted from DocAI using processor {processor}.")
    return result.document


# Move Google Cloud Storage file in blob format to new bucket and provides the option to delete from old
def move_blob(source_bucket_name, dest_bucket_name, blob_name):
    # source_bucket_name = string, name of source Google Cloud Storage bucket
    # dest_bucket_name = string, name of destination Google Cloud Storage bucket
    # blob_name = file name of Google Cloud Storage file in source bucket
    source_bucket = storage_client.get_bucket(source_bucket_name)
    dest_bucket = storage_client.get_bucket(dest_bucket_name)
    return


# Public to pubsub topic
def publish_to_pubsub(topic_path, message):
    # topic_path = path to topic, generated with: publisher.topic_path(project_id, topic_name)
    # message = data sent to pub/sub must be a bytestring
    future = publisher.publish(topic_path, message.encode("utf-8"))
    print(f"Result of publishing to PubSub topic:{future.result()}")


# Use for testing in local environment
def main():
    # make sure to export testing variables in variables.sh file
    event = {
        "bucket": f"{input_bucket_name}",
        "name": f"{file_name}",
        "contentType": f"{content_type}",
    }  # generic testing command
    # event = {'bucket': f"{input_bucket_name}", 'name':'something', 'contentType': f"{content_type}"}  #generic testing command
    context = ""
    process_receipt(event, context)


if __name__ == "__main__":
    main()
