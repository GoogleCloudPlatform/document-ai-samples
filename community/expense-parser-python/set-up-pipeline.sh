#! /bin/bash


DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

source "${DIR}/.env.local"

# create input bucket
gcloud storage buckets create --project ${PROJECT_ID} --default-storage-class standard --location ${BUCKET_LOCATION} --uniform-bucket-level-access gs://${PROJECT_ID}-input-receipts

# create archive bucket
gcloud storage buckets create --project ${PROJECT_ID} --default-storage-class standard --location ${BUCKET_LOCATION} --uniform-bucket-level-access gs://${PROJECT_ID}-archived-receipts

# create bucket to store rejected files
gcloud storage buckets create --project ${PROJECT_ID} --default-storage-class standard --location ${BUCKET_LOCATION} --uniform-bucket-level-access gs://${PROJECT_ID}-rejected-files

# create bq table
bq --location=US mk  -d \
--description "Parsing Results" \
${PROJECT_ID}:${BQ_DATASET_NAME}

bq mk --table ${BQ_DATASET_NAME}.${BQ_TABLE_NAME} table-schema/bq_schema.json

# deploy Cloud Function
gcloud functions deploy ${CLOUD_FUNCTION_NAME} \
--ingress-settings=${INGRESS_SETTINGS} \
--region=${CLOUD_FUNCTION_LOCATION} \
--entry-point=process_receipt \
--runtime=python37 \
--service-account=${CLOUD_FUNCTION_SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com \
--source=cloud-functions \
--timeout=400 \
--env-vars-file=cloud-functions/.env.yaml \
--trigger-resource=gs://${PROJECT_ID}-input-receipts \
--trigger-event=google.storage.object.finalize
