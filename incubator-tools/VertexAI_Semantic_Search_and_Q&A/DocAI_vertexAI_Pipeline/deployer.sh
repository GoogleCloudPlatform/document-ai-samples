#!/bin/bash

source input.sh

echo "--------------------------------------"
echo "######Check if the project exists#####"
echo "--------------------------------------"
# Check if the project exists  | Works!
if gcloud projects describe $PROJECT_ID &> /dev/null; then
  echo "Project $PROJECT_ID already exists. Please go further"
  gcloud config set project $PROJECT_ID
else
  echo "Project doesn't exists. Please use an exisiting project name"
fi
echo "--------------------------------------"
echo "######Check if the buckets exists#####"
echo "--------------------------------------"

# Check if the buckets exists  | Works!
if gsutil ls $PDF_INPUT_BUCKET_PATH &> /dev/null; then
  echo "Bucket $PDF_INPUT_BUCKET_PATH already exists."
else
  echo "Bucket $PDF_INPUT_BUCKET_PATH doesn't exists. Please use an
   existing bucket/create new one with the following shell command ::::: 
   gcloud storage buckets create gs://BUCKET_NAME 
  --project=PROJECT_NAME 
  --default-storage-class=STANDARD 
  --location=LOCATION 
  --uniform-bucket-level-access"
fi

if gsutil ls $DOCAI_PARSED_JSON_BUCKET_PATH &> /dev/null; then
  echo "Bucket $DOCAI_PARSED_JSON_BUCKET_PATH already exists."
else
  echo "Bucket $DOCAI_PARSED_JSON_BUCKET_PATH doesn't exists. Please use an
   existing bucket/create new one with the following shell command ::::: 
   gcloud storage buckets create gs://BUCKET_NAME 
  --project=PROJECT_NAME 
  --default-storage-class=STANDARD 
  --location=LOCATION 
  --uniform-bucket-level-access"
fi

if gsutil ls $CANONICAL_JSON_BUKCET_PATH &> /dev/null; then
  echo "Bucket $CANONICAL_JSON_BUKCET_PATH already exists."
else
  echo "Bucket $CANONICAL_JSON_BUKCET_PATH doesn't exists. Please use an
   existing bucket/create new one with the following shell command ::::: 
   gcloud storage buckets create gs://BUCKET_NAME 
  --project=PROJECT_NAME 
  --default-storage-class=STANDARD 
  --location=LOCATION 
  --uniform-bucket-level-access"
fi

if gsutil ls $JSONL_BUKCET_PATH &> /dev/null; then
  echo "Bucket $JSONL_BUKCET_PATH already exists."
else
  echo "Bucket $JSONL_BUKCET_PATH doesn't exists. Please use an
   existing bucket/create new one with the following shell command ::::: 
   gcloud storage buckets create gs://BUCKET_NAME 
  --project=PROJECT_NAME 
  --default-storage-class=STANDARD 
  --location=LOCATION 
  --uniform-bucket-level-access"
fi

echo "--------------------------------------"
echo "######Check if SA Account exists######"
echo "--------------------------------------"
#SA: if its existing, use it. else create SA and use it
if gcloud iam service-accounts describe $SERVICE_ACCOUNT_NAME &> /dev/null; then
    echo "SA $SERVICE_ACCOUNT_NAME already exists." 
    gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member "serviceAccount:$SERVICE_ACCOUNT_NAME" --role "roles/cloudfunctions.developer"

    gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member "serviceAccount:$SERVICE_ACCOUNT_NAME" --role "roles/run.invoker"

    gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member "serviceAccount:$SERVICE_ACCOUNT_NAME" --role "roles/documentai.editor"

    gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member "serviceAccount:$SERVICE_ACCOUNT_NAME" --role "roles/storage.admin"

    gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member "serviceAccount:$SERVICE_ACCOUNT_NAME" --role "roles/bigquery.dataEditor"

    gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member "serviceAccount:$SERVICE_ACCOUNT_NAME" --role "roles/iam.serviceAccountUser"

    gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member "serviceAccount:$SERVICE_ACCOUNT_NAME" --role "roles/iam.serviceAccountAdmin"

else
    # create SA for cloud function to use | works!
    echo "SA DOESN'T exists. CREATE a new one with the following command gcloud iam service-accounts 
    create SERVICE_ACCOUNT_NAME --display-name SERVICE_ACCOUNT_NAME"
fi

echo "--------------------------------------"
echo "######Create CF $PDF_TO_JSONL_CF ######"
echo "--------------------------------------"
if gcloud functions describe $PDF_TO_JSONL_CF &> /dev/null; then
  echo "Cloud Function job already exists."
else
    echo "Creating Cloud Function $PDF_TO_JSONL_CF."
    gcloud functions deploy $PDF_TO_JSONL_CF \
    --gen2 \
    --project=$PROJECT_ID \
    --runtime=python310 \
    --region=us-central1 \
    --source=pdf_to_jsonl_cf/ \
    --memory=4Gi \
    --cpu=2000m \
    --concurrency=100 \
    --min-instances=1 \
    --max-instances=100 \
    --timeout=3600 \
    --service-account=$SERVICE_ACCOUNT_NAME \
    --entry-point=pdf_jsonl \
    --trigger-http \
    --no-allow-unauthenticated
fi

# Here you get the output url endpoint of the deployed cloud function gen2 | save it to some variable and reuse it for scheduler uri | Working
PDF_TO_JSONL_CF_ENDPOINT=$(gcloud functions describe $PDF_TO_JSONL_CF \
--gen2 \
--region=us-central1 \
--format="value(url)")

echo "$PDF_TO_JSONL_CF endpoint : $PDF_TO_JSONL_CF_ENDPOINT"

echo "--------------------------------------"
echo "######Create CS $PDF_TO_JSONL_CF_CS ######"
echo "--------------------------------------"
# Check if the Cloud Scheduler job exists | Working
if gcloud scheduler jobs describe $PDF_TO_JSONL_CF_CS --location=us-central1 &> /dev/null; then
  echo "Cloud Scheduler job already exists."
else
  # Create the Cloud Scheduler job
  echo "Creating Cloud Scheduler."
  gcloud scheduler jobs create http $PDF_TO_JSONL_CF_CS \
  	--project=$PROJECT_ID \
    --schedule="0 * * * *" \
	--attempt-deadline="180s" \
    --location=us-central1 \
	--uri=$PDF_TO_JSONL_CF_ENDPOINT \
	--description="Triggers the cloud functions for checking any new files are added into the bucket" \
	--http-method="POST" \
	--headers='Content-Type=application/json, User-Agent=Google-Cloud-Scheduler' \
	--oidc-service-account-email=$SERVICE_ACCOUNT_NAME \
	--time-zone="Asia/Calcutta" \
	--message-body='{"BQ_PROJECT_NAME": "'"$BQ_PROJECT_NAME"'", "BQ_DATASET_NAME": "'"$BQ_DATASET_NAME"'","BQ_TABLE_NAME": "'"$BQ_TABLE_NAME"'",  
"PDF_INPUT_BUCKET_PATH": "'"$PDF_INPUT_BUCKET_PATH"'",  "DOCAI_PARSED_JSON_BUCKET_PATH": "'"$DOCAI_PARSED_JSON_BUCKET_PATH"'",  
"CANONICAL_JSON_BUKCET_PATH": "'"$CANONICAL_JSON_BUKCET_PATH"'", "PROJECT_ID": "'"$PROJECT_ID"'", 
"DOCAI_LOCATION": "'"$DOCAI_LOCATION"'",  "DOCAI_PROCESSOR_ID": "'"$DOCAI_PROCESSOR_ID"'",  
"DOCAI_PROCESSOR_VERSION_ID": "'"$DOCAI_PROCESSOR_VERSION_ID"'", "JSONL_BUKCET_PATH":"'"$JSONL_BUKCET_PATH"'"}'
fi

echo "--------------------------------------"
echo "######Create CF $JSONL_TO_VAIS_CF ######"
echo "--------------------------------------"
result="${JSONL_BUKCET_PATH##*/}"
if gcloud functions describe $JSONL_TO_VAIS_CF &> /dev/null; then
  echo "Cloud Function job already exists."
else
    echo "Creating Cloud Function $JSONL_TO_VAIS_CF."
    gcloud functions deploy $JSONL_TO_VAIS_CF \
    --gen2 \
    --project=$PROJECT_ID \
    --runtime=python310 \
    --region=us-central1 \
    --source=jsonl_to_vais_cf/ \
    --memory=1Gi \
    --cpu=1000m \
    --concurrency=100 \
    --min-instances=1 \
    --max-instances=100 \
    --timeout=540 \
    --service-account=$SERVICE_ACCOUNT_NAME \
    --entry-point=jsonl_vais \
    --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
    --trigger-event-filters="bucket=$result" \
    --trigger-service-account=$SERVICE_ACCOUNT_NAME
fi

# Here you get the output url endpoint of the deployed cloud function gen2 | save it to some variable and reuse it for scheduler uri | Working
JSONL_TO_VAIS_CF_ENDPOINT=$(gcloud functions describe $JSONL_TO_VAIS_CF \
--gen2 \
--region=us-central1 \
--format="value(url)")

echo "$JSONL_TO_VAIS_CF endpoint : $JSONL_TO_VAIS_CF_ENDPOINT"

echo "---------------------------------------------------------"
echo "######Replace PROJECT_NUMBER & DATASTORE_ID in html######"
echo "---------------------------------------------------------"
sed -i 's/PROJECT_NUMBER/'$PROJECT_NUMBER'/g' html/Faceted_Regulated_GenAI_Search.html
sed -i 's/VAIS_DATASTORE_ID/'$VAIS_DATASTORE_ID'/g' html/Faceted_Regulated_GenAI_Search.html

#Move the html file into input landing page directory 
gsutil cp html/Faceted_Regulated_GenAI_Search.html $CANONICAL_JSON_BUKCET_PATH/html/
CANONICAL_JSON_BUKCET="${CANONICAL_JSON_BUKCET_PATH##*/}"

echo "Open https://storage.mtls.cloud.google.com/$CANONICAL_JSON_BUKCET/html/Faceted_Regulated_GenAI_Search.html to play around the search"