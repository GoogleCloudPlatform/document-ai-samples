export PROJECT_ID=pdai-sandbox
export BUCKET_LOCATION=us-central1

export BIGQUERY_DATASET=dspa_invoices_uptrained
export BIGQUERY_TABLE=dspa_extracted_entities

export INPUT_BUCKET=gs://${PROJECT_ID}-input-invoices
export SPLIT_BUCKET=gs://${PROJECT_ID}-split-invoices
export OUTPUT_BUCKET=gs://${PROJECT_ID}-output-invoices
export ARCHIVE_BUCKET=gs://${PROJECT_ID}-archived-invoices

export SERVICE_ACCOUNT=${PROJECT_ID}@appspot.gserviceaccount.com

# Create BQ Dataset/Table
bq --location=US mk  -d \
--description "Invoice Parser Results" \
${PROJECT_ID}:${BIGQUERY_DATASET}

bq mk --table ${PROJECT_ID}:${BIGQUERY_DATASET}.${BIGQUERY_TABLE} doc_ai_extracted_entities.json

# Create Cloud Storage Buckets
gsutil mb -p ${PROJECT_ID} -c standard -l ${BUCKET_LOCATION} -b on ${INPUT_BUCKET}

gsutil mb -p ${PROJECT_ID} -c standard -l ${BUCKET_LOCATION} -b on ${SPLIT_BUCKET}

gsutil mb -p ${PROJECT_ID} -c standard -l ${BUCKET_LOCATION} -b on ${OUTPUT_BUCKET}

gsutil mb -p ${PROJECT_ID} -c standard -l ${BUCKET_LOCATION} -b on ${ARCHIVE_BUCKET}
