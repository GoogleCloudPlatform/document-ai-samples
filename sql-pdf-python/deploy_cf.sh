#!/bin/bash

#####################################################################################################
# Script Name: deploy_cf.sh
# Date of Creation: 12/01/2022
# Author: Ankur Wahi
# Updated: 12/02/2022
#####################################################################################################

source ./config.sh

project_id=${PROJECT_ID}
cf_create_docai="create-docai"
cf_process_docai="parser-docai"


echo "Deploying Doc AI CF"

cd ~/docai-on-bigquery/src/cloud-functions/create_docai

gcloud functions deploy ${cf_create_docai} --entry-point get_request --runtime python39 --trigger-http --allow-unauthenticated --project ${project_id} --service-account ${doc_sa} --gen2 --region ${REGION} --run-service-account ${doc_sa} --memory 256MB

endpoint_create_docai=$(gcloud functions describe ${cf_create_docai} --region=${REGION} --gen2 --format=json | jq -r '.serviceConfig.uri')


echo "Creating Doc AI Processor"

processor_id=$(curl -m 1010 -X POST ${endpoint_create_docai} -H "Authorization: bearer $(gcloud auth print-identity-token)" -H "Content-Type: application/json" -d '{
  "name": "Create Processor Trigger"
}')


cd ~/docai-on-bigquery/src/cloud-functions/process_docai

gcloud functions deploy ${cf_process_docai} --entry-point get_doc --runtime python39 --trigger-http --allow-unauthenticated --project ${project_id} --service-account ${doc_sa} --gen2 --region ${REGION} --run-service-account ${doc_sa} --memory 256MB

echo "Processor Id ${processor_id} has been created"


endpoint_parser_docai=$(gcloud functions describe ${cf_process_docai} --region=${REGION} --gen2 --format=json | jq -r '.serviceConfig.uri')


bq mk -d docai


build_sql="CREATE OR REPLACE FUNCTION docai.doc_extractor(uri STRING, content_type STRING, location STRING,docai_processorId STRING) RETURNS STRING REMOTE WITH CONNECTION \`${project_id}.us.gcf-docai-conn\` OPTIONS ( endpoint = '${endpoint_parser_docai}')"

    
bq query --use_legacy_sql=false ${build_sql}

echo "Creating bucket"

BUCKET_NAME=${PROJECT_ID}-docai-wahi
gcloud storage buckets create gs://${BUCKET_NAME}

echo "Bucket ${BUCKET_NAME} has been created"

echo "Uploading sample expense docs from data folder to ${BUCKET_NAME} "
gsutil cp ~/docai-on-bigquery/src/data/* gs://${BUCKET_NAME}

bq mk --external_table_definition=gs://${BUCKET_NAME}/*@projects/${PROJECT_ID}/locations/us/connections/gcf-docai-conn  --object_metadata=DIRECTORY  --max_staleness=0:30:0   --metadata_cache_mode=AUTOMATIC   --table docai.repos

sql_stmt="select docai.doc_extractor(uri,content_type,\"us\",\"${processor_id}\")  FROM docai.repos LIMIT 10"
bq query --use_legacy_sql=false ${sql_stmt}

