#!/bin/bash
# pylint: disable=C0103

"""Variables & Prompt user for project and function names"""

project_id=""
dataset_id=""
table_id=""
gcs_input_path="gs://{bucket-name}/{input-folder}/"
gcs_temp_path="gs://{bucket-name}/{temp-folder}/"
batch_size=30
gcs_output_uri="gs://{bucket-name}/{output-folder}/"
location=""
processor_id=""
Gcs_HITL_folder_path="gs://{bucket-name}/{HITL_folder}/"
critical_entities=["entity_1","entity_2"]
confidence_threshold=0.7
test_files_percentage=10

# variables for deploymnet
REGION="us-central1"
WORKFLOW_NAME="feedback-improvement-wf1"
YAML_FILE="workflow_1.yaml"
SERVICE_ACCOUNT=""
