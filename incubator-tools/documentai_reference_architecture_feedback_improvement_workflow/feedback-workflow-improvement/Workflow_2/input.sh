#!/bin/bash
# pylint: disable=C0103

"""Variables & Prompt user for project and function names"""

project_id=""
location=""
hitl_processor_id=""                                              # Processor ID where the Output of workflow 1 is imported.
post_HITL_output_URI="gs://{bucket-name}/{post_HITL_output_URI}/" # The path where the modified documents are present.
# For cloud function 2
pre_HITL_output_URI="gs://{bucket-name}/{pre_HITL_output_URI}/" # The path where the output of workflow 1 documents are present.
dataset_id=""
table_id=""
# For cloud function 3
gcs_backup_uri="gs://{bucket-name}/{gcs_backup_uri}/" # The path where the new processor dataset will be present.
train_processor_id=""                                 # New processor ID where training needs to be triggered.
# For cloud function 4
new_version_name="{version-name}"

# variables for deploymnet
REGION="us-central1"
WORKFLOW_NAME="feedback-improvement-wf2"
YAML_FILE="workflow_2.yaml"
SERVICE_ACCOUNT=""
