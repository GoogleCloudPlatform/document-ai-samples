#! /bin/bash


DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

source "${DIR}/.env.local"

# create archive bucket
gsutil mb -p ${PROJECT_ID} -c standard -l ${BUCKET_LOCATION} -b on gs://${PROJECT_ID}-archived-${COMPANY_NAME}-contracts

# create input bucket
gsutil mb -p ${PROJECT_ID} -c standard -l ${BUCKET_LOCATION} -b on gs://${PROJECT_ID}-input-${COMPANY_NAME}-contracts

# create output bucket
gsutil mb -p ${PROJECT_ID} -c standard -l ${BUCKET_LOCATION} -b on gs://${PROJECT_ID}-output-${COMPANY_NAME}-contracts

# create bucket to store rejected files
gsutil mb -p ${PROJECT_ID} -c standard -l ${BUCKET_LOCATION} -b on gs://${PROJECT_ID}-rejected-${COMPANY_NAME}-contracts

# create bq table
bq --location=US mk  -d \
--description "Parsing Results" \
${PROJECT_ID}:${BQ_DATASET_NAME}

bq mk --table ${BQ_DATASET_NAME}.${BQ_TABLE_NAME} table-schema/doc_ai_extracted_entities.json

# deploy Cloud Function
gcloud functions deploy process-contracts1 \
--ingress-settings=${INGRESS_SETTINGS} \
--region=${CLOUD_FUNCTION_LOCATION} \
--entry-point=process_contracts1 \
--runtime=python37 \
--service-account=${CLOUD_FUNCTION_SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com \
--source=cloud-functions \
--timeout=540 \
--memory=4096MB \
--env-vars-file=cloud-functions/.env.yaml \
--trigger-resource=gs://${PROJECT_ID}-input-${COMPANY_NAME}-contracts \
--trigger-event=google.storage.object.finalize
