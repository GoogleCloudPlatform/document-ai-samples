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

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "${DIR}/vars.sh"

PDIR=$(pwd)

cd "${DIR}/classify-job" || exit
echo "Build sample into a container"

gcloud builds submit --tag "$CLASSIFY_IMAGE_NAME"
cd "$PDIR" || exit


exists=$(gcloud run jobs describe "${CLASSIFY_JOB_NAME}" --region="$WORKFLOW_REGION" 2> /dev/null)
if [ -n "$exists" ]; then
  # Delete job if it already exists.
  echo "Deleting existing Job.. ${CLASSIFY_JOB_NAME}"
  gcloud run jobs delete "${CLASSIFY_JOB_NAME}" --region="$WORKFLOW_REGION" --quiet
else
  echo "Job ${CLASSIFY_JOB_NAME} does not exist..."
fi

echo "Creating ${CLASSIFY_JOB_NAME} using $CLASSIFY_IMAGE_NAME tasks"
gcloud run jobs create "${CLASSIFY_JOB_NAME}" \
    --image "${CLASSIFY_IMAGE_NAME}" \
    --command python \
    --args main.py \
    --region="$WORKFLOW_REGION" \
    --tasks 1 --task-timeout=50m \
    --set-env-vars=CLASSIFY_OUTPUT_BUCKET="$CLASSIFY_OUTPUT_BUCKET",CLASSIFY_INPUT_BUCKET="$CLASSIFY_INPUT_BUCKET",\
DOCAI_OUTPUT_BUCKET="$DOCAI_OUTPUT_BUCKET" \
    --set-env-vars=REGION="$WORKFLOW_REGION",OUTPUT_FILE_JSON="$OUTPUT_FILE_JSON",OUTPUT_FILE_CSV="$OUTPUT_FILE_CSV",\
OUTPUT_FILE_JSON="$OUTPUT_FILE_JSON",OUTPUT_FILE_CSV="$OUTPUT_FILE_CSV" \
    --set-env-vars=BQ_DATASET_ID_MLOPS="$BQ_DATASET_ID_MLOPS",BQ_OBJECT_TABLE_RETENTION_DAYS="$BQ_OBJECT_TABLE_RETENTION_DAYS",\
BQ_DATASET_ID_PROCESSED_DOCS="$BQ_DATASET_ID_PROCESSED_DOCS",BQ_REGION="$REGION",BQ_PROJECT_ID="$BQ_PROJECT_ID",\
BQ_GCS_CONNECTION_NAME="$BQ_GCS_CONNECTION_NAME",SPLITTER_OUTPUT_DIR="$SPLITTER_OUTPUT_DIR" \
    --service-account="$SERVICE_ACCOUNT_CLASSIFY_JOB_EMAIL"


echo "Deploy workflow: $WORKFLOW_NAME"
gcloud workflows deploy "$WORKFLOW_NAME" \
  --source=classify-extract.yaml \
  --location="$WORKFLOW_REGION" \
  --set-env-vars CLASSIFY_INPUT_BUCKET="$CLASSIFY_INPUT_BUCKET",CLASSIFY_OUTPUT_BUCKET="$CLASSIFY_OUTPUT_BUCKET",\
CLASSIFY_JOB_NAME="$CLASSIFY_JOB_NAME",REGION="$WORKFLOW_REGION",DATA_SYNCH="$DATA_SYNCH",\
SPLITTER_OUTPUT_DIR="$SPLITTER_OUTPUT_DIR"\
  --service-account="${SERVICE_ACCOUNT_WORKFLOW_EMAIL}"
