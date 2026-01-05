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

# Enable APIs
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    eventarc.googleapis.com \
    logging.googleapis.com \
    cloudbuild.googleapis.com \
    workflows.googleapis.com \
    pubsub.googleapis.com \
    documentai.googleapis.com \
    compute.googleapis.com --project="$PROJECT_ID"


gcloud config set eventarc/location "${REGION}"
gcloud config set run/region "${REGION}"

create_service_account() {
  SA_NAME=$1
  if gcloud iam service-accounts list --project "$PROJECT_ID" | grep -q $SA_NAME; then
    echo "Service account $SA_NAME has been found."
  else
    echo "Creating Service Account $SA_NAME... "
    gcloud iam service-accounts create $SA_NAME
  fi
}


create_dataset() {
  BQ_DATASET_ID=$1
  if bq show --dataset "${BQ_PROJECT_ID}:${BQ_DATASET_ID}" >/dev/null 2>&1; then
      echo "Dataset ${BQ_DATASET_ID} already exists in project ${BQ_PROJECT_ID}. Skipping creation."
  else
      echo "Creating dataset ${BQ_DATASET_ID} in project ${BQ_PROJECT_ID}..."

      if bq mk --dataset --location="${REGION}" "${BQ_PROJECT_ID}:${BQ_DATASET_ID}"; then
          echo "Dataset ${BQ_DATASET_ID} created successfully."
      else
          echo "Failed to create dataset ${BQ_DATASET_ID}. Please check permissions and configuration." >&2
          exit 1
      fi
  fi
}

create_bucket () {
  BUCKET_NAME=$1
  VERSIONING=$2

  gcloud storage ls "gs://${BUCKET_NAME}" 2> /dev/null
  RETURN=$?
  if [[ $RETURN -gt 0 ]]; then
      gcloud storage buckets create gs://"${BUCKET_NAME}" --location "$REGION"
      if [ -n "$VERSIONING" ]; then
        echo "Enabling versioning on gs://${BUCKET_NAME} "
        gcloud storage buckets update gs://${BUCKET_NAME} --versioning
      fi
  else
      echo "Bucket $BUCKET_NAME exists, skipping creation"
  fi
}

##################################
# Prepare for Classify Job
##################################
create_bucket "$DOCAI_OUTPUT_BUCKET"
create_bucket "$CLASSIFY_INPUT_BUCKET"
create_bucket "$CLASSIFY_OUTPUT_BUCKET"
create_bucket "$CONFIG_BUCKET" "on"

# TODO Copy local config to GCS, Create FORm parser. Should be working with FORM parser out of the box

create_service_account "$SERVICE_ACCOUNT_CLASSIFY_JOB"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --role roles/logging.logWriter \
  --member serviceAccount:"${SERVICE_ACCOUNT_CLASSIFY_JOB_EMAIL}"

# to output classify.json file
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --role roles/storage.admin \
  --member serviceAccount:"${SERVICE_ACCOUNT_CLASSIFY_JOB_EMAIL}"

# To be able to trigger the callbacks
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --role roles/workflows.invoker \
  --member serviceAccount:"${SERVICE_ACCOUNT_CLASSIFY_JOB_EMAIL}"

# DOCAI Access
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --role roles/documentai.viewer \
  --member serviceAccount:"${SERVICE_ACCOUNT_CLASSIFY_JOB_EMAIL}"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --role roles/documentai.apiUser \
  --member serviceAccount:"${SERVICE_ACCOUNT_CLASSIFY_JOB_EMAIL}"

# BigQuery to create jobs
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --role roles/bigquery.admin \
  --member serviceAccount:"${SERVICE_ACCOUNT_CLASSIFY_JOB_EMAIL}"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --role roles/bigquery.jobUser \
  --member serviceAccount:"${SERVICE_ACCOUNT_CLASSIFY_JOB_EMAIL}"


# For Cross Project Access
if [ -n "$DOCAI_PROJECT_ID" ]; then
  if [ "$DOCAI_PROJECT_ID" != "$PROJECT_ID" ]; then
    echo "Setting Up cross project access for $DOCAI_PROJECT_ID"
    PROJECT_DOCAI_NUMBER=$(gcloud projects describe "$DOCAI_PROJECT_ID" --format='get(projectNumber)')
    SA_DOCAI="service-${PROJECT_DOCAI_NUMBER}@gcp-sa-prod-dai-core.iam.gserviceaccount.com"
    gcloud storage buckets add-iam-policy-binding  gs://${DOCAI_OUTPUT_BUCKET} --member="serviceAccount:$SA_DOCAI" --role="roles/storage.admin"
    gcloud storage buckets add-iam-policy-binding  gs://${CLASSIFY_INPUT_BUCKET} --member="serviceAccount:$SA_DOCAI" --role="roles/storage.objectViewer"

    gcloud projects add-iam-policy-binding "$DOCAI_PROJECT_ID" --member="serviceAccount:${SERVICE_ACCOUNT_CLASSIFY_JOB_EMAIL}"  --role="roles/documentai.viewer"
    gcloud projects add-iam-policy-binding "$DOCAI_PROJECT_ID" --member="serviceAccount:${SERVICE_ACCOUNT_CLASSIFY_JOB_EMAIL}"  --role="roles/documentai.apiUser"
  fi

fi

echo "Roles assigned for $SERVICE_ACCOUNT_CLASSIFY_JOB_EMAIL:"
gcloud projects get-iam-policy "$PROJECT_ID"  \
--flatten="bindings[].members" \
--format='table(bindings.role)' \
--filter="bindings.members:${SERVICE_ACCOUNT_CLASSIFY_JOB_EMAIL}"


# Required for the Build
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member serviceAccount:"${SERVICE_ACCOUNT_COMPUTE_EMAIL}" \
    --role="roles/storage.objectUser"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member serviceAccount:"${SERVICE_ACCOUNT_COMPUTE_EMAIL}" \
    --role="roles/artifactregistry.createOnPushWriter"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member serviceAccount:"${SERVICE_ACCOUNT_COMPUTE_EMAIL}" \
    --role="roles/logging.logWriter"


exists=$(gcloud artifacts repositories describe --location="${REGION}" "${REPOSITORY}" 2> /dev/null)
if [ -z "$exists" ]; then
  echo "Creating ${REPOSITORY} repo in project ${PROJECT_ID}..."
  gcloud artifacts repositories create "${REPOSITORY}" \
    --project="${PROJECT_ID}" \
    --repository-format=docker \
    --location="${REGION}"
else
  echo "Repository ${REPOSITORY} already exists in project ${PROJECT_ID}..."
fi


##################################
# Prepare for Workflow
##################################
create_service_account "$SERVICE_ACCOUNT_WORKFLOW"

# Grant the eventarc.eventReceiver role, so the service account can be used in a Cloud Storage trigger:
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --role roles/eventarc.eventReceiver \
  --member serviceAccount:"${SERVICE_ACCOUNT_WORKFLOW_EMAIL}"

# To Log
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --role roles/logging.logWriter \
  --member serviceAccount:"${SERVICE_ACCOUNT_WORKFLOW_EMAIL}"

# To read from GCS
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --role roles/storage.objectUser \
  --member serviceAccount:"${SERVICE_ACCOUNT_WORKFLOW_EMAIL}"

# To invoke Cloud Run Job
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --role roles/run.invoker \
  --member serviceAccount:"${SERVICE_ACCOUNT_WORKFLOW_EMAIL}"

#  To run.jobs.runWithOverrides
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --role roles/run.admin \
  --member serviceAccount:"${SERVICE_ACCOUNT_WORKFLOW_EMAIL}"

# For BigQuery Access
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --role roles/bigquery.jobUser \
  --member serviceAccount:"${SERVICE_ACCOUNT_WORKFLOW_EMAIL}"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --role roles/bigquery.connectionUser \
  --member serviceAccount:"${SERVICE_ACCOUNT_WORKFLOW_EMAIL}"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --role roles/bigquery.dataEditor \
  --member serviceAccount:"${SERVICE_ACCOUNT_WORKFLOW_EMAIL}"


echo "Roles assigned for $SERVICE_ACCOUNT_WORKFLOW_EMAIL:"
gcloud projects get-iam-policy $PROJECT_ID  \
--flatten="bindings[].members" \
--format='table(bindings.role)' \
--filter="bindings.members:${SERVICE_ACCOUNT_WORKFLOW_EMAIL}"


##################################
# Create a Cloud Storage trigger
##################################
gcloud storage buckets add-iam-policy-binding gs://"${CLASSIFY_INPUT_BUCKET}" --member="serviceAccount:${SERVICE_ACCOUNT_CLASSIFY_JOB_EMAIL}" --role="roles/storage.objectViewer"

# You also need to add the pubsub.publisher role to the Cloud Storage service account for Cloud Storage triggers:
SERVICE_ACCOUNT_STORAGE=$(gcloud storage service-agent --project $PROJECT_ID)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member serviceAccount:$SERVICE_ACCOUNT_STORAGE \
    --role="roles/pubsub.publisher"

# Create service account to represent the Pub/Sub subscription identity.
create_service_account $SERVICE_ACCOUNT_EVENTARC_TRIGGER

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member serviceAccount:"${SERVICE_ACCOUNT_EVENTARC_TRIGGER_EMAIL}" \
    --role="roles/eventarc.eventReceiver"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member serviceAccount:"${SERVICE_ACCOUNT_EVENTARC_TRIGGER_EMAIL}" \
    --role="roles/workflows.invoker"

echo "Deploy workflow: $WORKFLOW_NAME"
gcloud workflows deploy "$WORKFLOW_NAME" \
  --source=classify-extract.yaml \
  --location="$WORKFLOW_REGION" \
  --set-env-vars CLASSIFY_INPUT_BUCKET="$CLASSIFY_INPUT_BUCKET",CLASSIFY_OUTPUT_BUCKET="$CLASSIFY_OUTPUT_BUCKET",CLASSIFY_JOB_NAME="$CLASSIFY_JOB_NAME",REGION="$REGION"\
  --service-account="${SERVICE_ACCOUNT_WORKFLOW_EMAIL}"

# Create a trigger to route new file creation events from the bucket to your service:
if gcloud eventarc triggers describe "$WORKFLOW_TRIGGER_NAME" 2>/dev/null; then
    echo "Trigger '$WORKFLOW_TRIGGER_NAME' already exists. Skipping..."
else
    echo "Creating trigger '$WORKFLOW_TRIGGER_NAME'..."
    gcloud eventarc triggers create $WORKFLOW_TRIGGER_NAME \
      --destination-workflow=$WORKFLOW_NAME \
      --destination-workflow-location=$WORKFLOW_REGION \
      --event-filters="type=google.cloud.storage.object.v1.finalized" \
      --event-filters="bucket=$CLASSIFY_INPUT_BUCKET" \
      --location="$REGION" \
      --service-account="$SERVICE_ACCOUNT_EVENTARC_TRIGGER_EMAIL"
fi


##################################
# Big Query Setup
##################################
# Create dataset
create_dataset "$BQ_DATASET_ID_PROCESSED_DOCS"
create_dataset "$BQ_DATASET_ID_MLOPS"


# Create Cloud Resource Connection
if bq show --connection "${BQ_PROJECT_ID}.${REGION}.${BQ_GCS_CONNECTION_NAME}" >/dev/null 2>&1; then
    echo "Cloud Connection ${BQ_GCS_CONNECTION_NAME} already exists in project ${BQ_PROJECT_ID}. Skipping creation."
else
    echo "Creating Cloud Connection ${BQ_GCS_CONNECTION_NAME} in project ${BQ_PROJECT_ID}..."

    if bq mk --connection \
       --location="${REGION}" \
       --project_id="${BQ_PROJECT_ID}" \
       --connection_type=CLOUD_RESOURCE \
       "${BQ_GCS_CONNECTION_NAME}"; then
        echo "Cloud Connection ${BQ_GCS_CONNECTION_NAME} created successfully."
    else
        echo "Failed to create Cloud Connection ${BQ_GCS_CONNECTION_NAME}. Please check permissions and configuration." >&2
        exit 1
    fi
fi


# Retrieve and copy the service account ID for use in a later step
bq show --connection $BQ_PROJECT_ID.$REGION.$BQ_GCS_CONNECTION_NAME
connection_details=$(bq show --connection  "$BQ_PROJECT_ID.$REGION.$BQ_GCS_CONNECTION_NAME")


# Extract the service account email using regular expressions
if [[ $connection_details =~ serviceAccountId\":\ \"([^\"]+)\" ]]; then
    service_account="${BASH_REMATCH[1]}"
    echo service_account="$service_account"
    gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:"${service_account}" --role=roles/documentai.viewer
    gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:"${service_account}" --role=roles/documentai.apiUser
    gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:"${service_account}" --role=roles/storage.objectViewer

    if [ "$DOCAI_PROJECT_ID" != "$PROJECT_ID" ]; then
      gcloud projects add-iam-policy-binding $DOCAI_PROJECT_ID --member=serviceAccount:"${service_account}" --role=roles/documentai.apiUser
      gcloud projects add-iam-policy-binding $DOCAI_PROJECT_ID --member=serviceAccount:"${service_account}" --role=roles/documentai.viewer
    fi
else
    echo "Service account email not found in connection $CONNECTION_NAME" >&2
    exit 1  # Indicate failure
fi


##################################
# Deploy
##################################

bash -e "${DIR}/deploy.sh"