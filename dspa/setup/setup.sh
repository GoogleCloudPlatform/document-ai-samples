export PROJECT_ID=YOUR_PROJECT_ID
export BUCKET_LOCATION=us-central1

export INPUT_BUCKET=gs://${PROJECT_ID}-input-invoices
export OUTPUT_BUCKET=gs://${PROJECT_ID}-output-invoices
export ARCHIVE_BUCKET=gs://${PROJECT_ID}-archived-invoices

export SERVICE_ACCOUNT=${PROJECT_ID}@appspot.gserviceaccount.com

# Create BQ Dataset/Table
bq --location=US mk  -d \
--description "Invoice Parser Results" \
${PROJECT_ID}:invoice_parser_results

bq mk --table ${PROJECT_ID}:invoice_parser_results.doc_ai_extracted_entities doc_ai_extracted_entities.json

# Create Cloud Storage Buckets
gsutil mb -p ${PROJECT_ID} -c standard -l ${BUCKET_LOCATION} -b on ${INPUT_BUCKET}

gsutil mb -p ${PROJECT_ID} -c standard -l ${BUCKET_LOCATION} -b on ${OUTPUT_BUCKET}

gsutil mb -p ${PROJECT_ID} -c standard -l ${BUCKET_LOCATION} -b on ${ARCHIVE_BUCKET}
