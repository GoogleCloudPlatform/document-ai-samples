#!/bin/bash

# TODO: for local testing. Replace variable names with your environment variables
export GCP_PROJECT="<GCP PROJECT ID>"
export INPUT_BUCKET="<ORIGINAL INPUT BUCKET>"
export GCP_PROJECT_NAME="<GCP PROJECT NAME>"
export PARSER_LOCATION=us
export PROCESSOR_ID_Q="<loan_workshop_doc_quality ID>"
export PROCESSOR_ID_CLASS="<loan_workshop_classifier ID>"
export PROCESSOR_ID_1040="<loan_workshop_1040c_parser ID>"
export PROCESSOR_ID_1120="<loan_workshop_1120sk1_parser ID>"
export BQ_DATASET_NAME="<BQ DATASET NAME>"
export BQ_TABLE_NAME="<BQ TABLE NAME>" 
export BUCKET_1040C_PROCESSED="<1040C PROCESSED BUCKET>"
export BUCKET_1120S_PROCESSED="<1120S PROCESSED BUCKET>"
export BUCKET_1040C_INPUT="<1040C INPUT BUCKET>"
export BUCKET_1120S_INPUT="<1120S INPUT BUCKET>"
export BUCKET_REJECTED="<REJECTED DOC BUCKET>"
export PUBSUB_UIL_REVIEW_TOPIC_NAME="<PUB/SUB TOPIC NAME TO BE REVIEWED>"
export PUBSUB_WORKFLOW_TOPIC_NAME="<PUB/SUB TOPIC NAME FOR APPROVED>"
export FILE_NAME="<file name in input bucket>"
export CONTENT_TYPE="<file type of testing document>"
