#!/bin/bash

source input.sh

echo "********************************************************************************"
echo "********************************************************************************"

# Deploy Cloud Function 1
echo "Deploying export_hitl_reviewed_docs Cloud Function..."
gcloud functions deploy export_hitl_reviewed_docs \
    --gen2 \
    --runtime python310 \
    --trigger-http \
    --allow-unauthenticated \
    --entry-point export_hitl_reviewed_docs \
    --region $REGION \
    --source export_hitl_reviewed_docs \
    --service-account $SERVICE_ACCOUNT \
    --run-service-account $SERVICE_ACCOUNT \
    --memory 1GB
    
echo "********************************************************************************"
echo "********************************************************************************"

# Deploy Cloud Function 2
echo "Deploying hitl_analysis Cloud Function..."
gcloud functions deploy hitl_analysis \
    --gen2 \
    --runtime python310 \
    --trigger-http \
    --allow-unauthenticated \
    --entry-point hitl_analysis \
    --region $REGION \
    --source hitl_analysis \
    --service-account $SERVICE_ACCOUNT \
    --run-service-account $SERVICE_ACCOUNT \
    --memory 512MB
    
echo "********************************************************************************"
echo "********************************************************************************"

# Deploy Cloud Function 3
echo "Deploying dataset_export_import Cloud Function..."
gcloud functions deploy dataset_export_import \
    --gen2 \
    --runtime python310 \
    --trigger-http \
    --allow-unauthenticated \
    --entry-point dataset_export_import \
    --region $REGION \
    --source dataset_export_import \
    --service-account $SERVICE_ACCOUNT \
    --run-service-account $SERVICE_ACCOUNT \
    --memory 256MB

echo "********************************************************************************"
echo "********************************************************************************"

# Deploy cloud function to load files to BigQuery and trigger submit_batch
echo "Deploying trigger_training Cloud function"
gcloud functions deploy trigger_training \
    --gen2 \
    --runtime python310 \
    --trigger-http \
    --allow-unauthenticated \
    --entry-point process_training_request \
    --region $REGION \
    --source trigger_training \
    --service-account $SERVICE_ACCOUNT \
    --run-service-account $SERVICE_ACCOUNT \
    --memory 256MB
    
echo "********************************************************************************"
echo "********************************************************************************"

# Create the workflow
gcloud workflows deploy $WORKFLOW_NAME \
  --location=$REGION \
  --source=$YAML_FILE \
  --project=$project_id \
  --service-account=$SERVICE_ACCOUNT

# Build the JSON string dynamically
INPUT_JSON=$(jq -n \
  --arg project_id $project_id \
  --arg location $location  \
  --arg hitl_processor_id $hitl_processor_id  \
  --arg pre_HITL_output_URI $pre_HITL_output_URI  \
  --arg post_HITL_output_URI $post_HITL_output_URI  \
  --arg dataset_id $dataset_id  \
  --arg table_id $table_id  \
  --arg gcs_backup_uri $gcs_backup_uri  \
  --arg train_processor_id $train_processor_id  \
  --arg new_version_name $new_version_name \
  '{project_id: $project_id, location: $location, hitl_processor_id: $hitl_processor_id, pre_HITL_output_URI: $pre_HITL_output_URI, post_HITL_output_URI: $post_HITL_output_URI, dataset_id: $dataset_id, table_id: $table_id, gcs_backup_uri: $gcs_backup_uri, train_processor_id: $train_processor_id, new_version_name: $new_version_name}')

# echo \'"$INPUT_JSON"\'

# Trigger the workflow
gcloud workflows run $WORKFLOW_NAME \
  --location=$REGION \
  --project=$project_id \
  --data="$INPUT_JSON"

echo "********************************************************************************"
echo "********************************************************************************"

echo "Workflow triggered"

echo "********************************************************************************"
echo "********************************************************************************"