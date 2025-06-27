#!/bin/bash

source input.sh

echo "********************************************************************************"
echo "********************************************************************************"

# Deploy Cloud Function 1
echo "Deploying bqdataset_input Cloud Function..."
gcloud functions deploy bqdataset_input \
    --gen2 \
    --runtime python310 \
    --trigger-http \
    --allow-unauthenticated \
    --entry-point bqdataset \
    --region $REGION \
    --source bqdataset_input \
    --service-account $SERVICE_ACCOUNT \
    --run-service-account $SERVICE_ACCOUNT \
    --memory 256MB

echo "********************************************************************************"
echo "Status : $?"
if [ $? -ne 0 ]; then
    echo "Cloud function deployment failed"
    return -1
else
    echo "Cloud function deployed"
fi
echo "********************************************************************************"

# Deploy Cloud Function 2
echo "Deploying split_batches Cloud Function..."
gcloud functions deploy split_batches \
    --gen2 \
    --runtime python310 \
    --trigger-http \
    --allow-unauthenticated \
    --entry-point split_copy_files \
    --region $REGION \
    --source split_batches \
    --service-account $SERVICE_ACCOUNT \
    --run-service-account $SERVICE_ACCOUNT \
    --memory 256MB

echo "********************************************************************************"
if [ $? -ne 0 ]; then
    echo "Cloud function deployment failed"
    return -1
else
    echo "Cloud function deployed"
fi
echo "********************************************************************************"

# Deploy Cloud Function 3
echo "Deploying batch_process Cloud Function..."
gcloud functions deploy batch_process \
    --gen2 \
    --runtime python310 \
    --trigger-http \
    --allow-unauthenticated \
    --entry-point concurrent_batch_process \
    --region $REGION \
    --source batch_process \
    --service-account $SERVICE_ACCOUNT \
    --run-service-account $SERVICE_ACCOUNT \
    --memory 256MB \
    --timeout 3600


echo "********************************************************************************"
if [ $? -ne 0 ]; then
    echo "Cloud function deployment failed"
    return -1
else
    echo "Cloud function deployed"
fi
echo "********************************************************************************"

# Deploy Cloud Function 4
echo "Deploying hitl_criteria_check Cloud function"
gcloud functions deploy hitl_criteria_check \
    --gen2 \
    --runtime python310 \
    --trigger-http \
    --allow-unauthenticated \
    --entry-point HITL_Feedback \
    --region $REGION \
    --source hitl_criteria_check \
    --service-account $SERVICE_ACCOUNT \
    --run-service-account $SERVICE_ACCOUNT \
    --memory 2GB

echo "********************************************************************************"
if [ $? -ne 0 ]; then
    echo "Cloud function deployment failed"
    return -1
else
    echo "Cloud function deployed"
fi
echo "********************************************************************************"

# Create the workflow
gcloud workflows deploy $WORKFLOW_NAME \
  --location=$REGION \
  --source=$YAML_FILE \
  --project=$project_id \
  --service-account=$SERVICE_ACCOUNT

echo "********************************************************************************"
if [ $? -ne 0 ]; then
    echo "Workflow deployment failed"
    return -1
else
    echo "Workflow deployed"
fi
echo "********************************************************************************"

# Build the JSON string dynamically
INPUT_JSON=$(jq -n \
  --arg Gcs_HITL_folder_path $Gcs_HITL_folder_path  \
  --argjson batch_size $batch_size  \
  --argjson confidence_threshold $confidence_threshold \
  --arg critical_entities $critical_entities  \
  --arg dataset_id $dataset_id  \
  --arg gcs_input_path $gcs_input_path  \
  --arg gcs_output_uri $gcs_output_uri  \
  --arg location $location  \
  --arg processor_id $processor_id  \
  --arg project_id $project_id \
  --arg table_id $table_id  \
  --argjson test_files_percentage $test_files_percentage \
  --arg gcs_temp_path $gcs_temp_path  \
  '{project_id: $project_id, dataset_id: $dataset_id, table_id: $table_id, gcs_input_path: $gcs_input_path, gcs_temp_path: $gcs_temp_path, batch_size: $batch_size, gcs_output_uri: $gcs_output_uri, location: $location, processor_id: $processor_id, Gcs_HITL_folder_path: $Gcs_HITL_folder_path, critical_entities: $critical_entities, confidence_threshold: $confidence_threshold, test_files_percentage: $test_files_percentage}')

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
