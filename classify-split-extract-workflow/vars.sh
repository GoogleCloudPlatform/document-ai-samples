#!/bin/bash

# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

export REGION=us # Multi-regional
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='get(projectNumber)')
export PROJECT_NUMBER
export REPOSITORY=cloudrun

# Classification Job
export CLASSIFY_INPUT_BUCKET="${PROJECT_ID}-documents"
export CLASSIFY_OUTPUT_BUCKET="${PROJECT_ID}-workflow"
export DOCAI_OUTPUT_BUCKET="${PROJECT_ID}-docai-output"
export CLASSIFY_JOB_NAME="classify-job"
export CLASSIFY_IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${CLASSIFY_JOB_NAME}"
export SERVICE_ACCOUNT_CLASSIFY_JOB="classify-job-sa"
export SERVICE_ACCOUNT_CLASSIFY_JOB_EMAIL="${SERVICE_ACCOUNT_CLASSIFY_JOB}@${PROJECT_ID}.iam.gserviceaccount.com"
export SERVICE_ACCOUNT_COMPUTE_EMAIL=${PROJECT_NUMBER}-compute@developer.gserviceaccount.com
export OUTPUT_FILE_JSON="classify_output.json"
export OUTPUT_FILE_CSV="classify_output.csv"
export SPLITTER_OUTPUT_DIR="splitter_output"

# Workflow
export WORKFLOW_NAME="classify-extract"
export WORKFLOW_REGION="us-central1"
export SERVICE_ACCOUNT_WORKFLOW="classify-extract-wf-sa"
export SERVICE_ACCOUNT_WORKFLOW_EMAIL="${SERVICE_ACCOUNT_WORKFLOW}@${PROJECT_ID}.iam.gserviceaccount.com"
export AUTO_EXTRACT="true" # To support auto triggering of extraction when classification is complete
export DATA_SYNCH="true" # To support processing on each pdf file upload (be mindful of quota being 5 concurrent API requests)

# Event Arc To trigger Workflow
export WORKFLOW_TRIGGER_NAME="workflow-trigger-storage"
export SERVICE_ACCOUNT_EVENTARC_TRIGGER="eventarc-trigger-sa"
export SERVICE_ACCOUNT_EVENTARC_TRIGGER_EMAIL="${SERVICE_ACCOUNT_EVENTARC_TRIGGER}@${PROJECT_ID}.iam.gserviceaccount.com"

# GCS
export DOCAI_OUTPUT_BUCKET="${PROJECT_ID}-docai-output"
export CONFIG_BUCKET="${PROJECT_ID}-config"

# BQ
export BQ_PROJECT_ID=$PROJECT_ID
export BQ_DATASET_ID_PROCESSED_DOCS="processed_documents"
export BQ_DATASET_ID_MLOPS="mlops"
export BQ_OBJECT_TABLE_RETENTION_DAYS=7
export BQ_GCS_CONNECTION_NAME="bq-connection-gcs"

echo "Using PROJECT_ID=$PROJECT_ID, REGION=$REGION, WORKFLOW_REGION=$WORKFLOW_REGION"
# payload to test workflow manually
#   {"bucket": "cda-prior-auth-02-documents", "data": { "name": "START_PIPELINE"}}
