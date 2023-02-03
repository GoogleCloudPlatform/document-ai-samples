#! /bin/bash


DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

source "${DIR}/.env.local"

# create archive bucket
gsutil mb -p ${PROJECT_ID} -c standard -l ${BUCKET_LOCATION} -b on gs://${PROJECT_ID}-archived-petsmart-invoices

# create input bucket
gsutil mb -p ${PROJECT_ID} -c standard -l ${BUCKET_LOCATION} -b on gs://${PROJECT_ID}-input-petsmart-invoices

# create output bucket
gsutil mb -p ${PROJECT_ID} -c standard -l ${BUCKET_LOCATION} -b on gs://${PROJECT_ID}-output-petsmart-invoices

# create bucket to store rejected files
gsutil mb -p ${PROJECT_ID} -c standard -l ${BUCKET_LOCATION} -b on gs://${PROJECT_ID}-rejected-petsmart-files

# create bq table
bq --location=US mk  -d \
--description "Parsing Results" \
${PROJECT_ID}:${BQ_DATASET_NAME}

bq mk --table ${BQ_DATASET_NAME}.${BQ_TABLE_NAME} table-schema/doc_ai_extracted_entities.json

# deploy Cloud Function
gcloud functions deploy process-invoices \
--ingress-settings=${INGRESS_SETTINGS} \
--region=${CLOUD_FUNCTION_LOCATION} \
--entry-point=process_receipt \
--runtime=python37 \
--service-account=${CLOUD_FUNCTION_SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com \
--source=cloud-functions \
--timeout=400 \
--env-vars-file=cloud-functions/.env.yaml \
--trigger-resource=gs://${PROJECT_ID}-input-petsmart-invoices \
--trigger-event=google.storage.object.finalize
