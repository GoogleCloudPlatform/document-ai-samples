#!/bin/bash

# Prompt user for project and function names
BQ_PROJECT_NAME="Bigquery project name"
BQ_DATASET_NAME="xxxxx" #existing one or mention a new name if required to create a new dataset
BQ_TABLE_NAME="xxxxx" #existing one or mention a new name if required to create a new dataset
PDF_INPUT_BUCKET_PATH="gs://{input-bucket-path}" #include gs://
DOCAI_PARSED_JSON_BUCKET_PATH="gs://{parsed_json_bucket}" #include gs://
CANONICAL_JSON_BUKCET_PATH="gs://{canonical_jsons_bucket}" #include gs://
JSONL_BUKCET_PATH="gs://{vertexai_metadata_jsonl_bucket}" #include gs://
PROJECT_ID="project-id"
PROJECT_NUMBER="xxxxxxx"
DOCAI_LOCATION="xxxx"
DOCAI_PROCESSOR_ID="xxxxxxxxx"
DOCAI_PROCESSOR_VERSION_ID="pretrained-invoice-v2.0-2023-12-06"
PDF_TO_JSONL_CF="pdf_to_jsonl_cf" #Cloud Function
PDF_TO_JSONL_CF_CS="pdf_to_jsonl_cf_cs" #Cloud Scheduler
JSONL_TO_VAIS_CF="jsonl_to_vais_cf" #Cloud Function with trigger on JSONL_BUKCET_PATH
VAIS_DATASTORE_ID="pdf-json_1699996276496"
SERVICE_ACCOUNT_NAME="service-account@project.iam.gserviceaccount.com" # here is the example service account name.