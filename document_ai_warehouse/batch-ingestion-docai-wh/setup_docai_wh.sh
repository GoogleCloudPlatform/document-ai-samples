#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

LOG="$DIR/setup.log"
filename=$(basename $0)
timestamp=$(date +"%m-%d-%Y_%H:%M:%S")
echo "$timestamp - Running $filename ... " | tee "$LOG"

source "${DIR}/SET"
gcloud config set project $DOCAI_WH_PROJECT_ID

if [[ -z "${DOCAI_WH_PROJECT_ID}" ]]; then
  echo DOCAI_WH_PROJECT_ID env variable is not set.  | tee -a "$LOG"
  exit
fi

if [[ -z "${DOCAI_PROJECT_ID}" ]]; then
  echo DOCAI_PROJECT_ID env variable is not set.  | tee -a "$LOG"
  exit
fi

if [[ -z "${DATA_PROJECT_ID}" ]]; then
  echo DATA_PROJECT_ID env variable is not set.  | tee -a "$LOG"
  exit
fi

export PROJECT_ID=$DOCAI_WH_PROJECT_ID

#if [[ -z "${PROCESSOR_ID}" ]]; then
#  echo PROCESSOR_ID env variable is not set.  | tee -a "$LOG"
#  exit
#fi

#pip install -r requirements.txt  | tee -a "$LOG"

#gcloud auth application-default login

echo "Disabling Organization Policy preventing Service Account Key Creation.. " | tee -a "$LOG"
gcloud services enable orgpolicy.googleapis.com | tee -a "$LOG"

enabled=$(gcloud services list --enabled | grep orgpolicy)
while [ -z "$enabled" ]; do
  enabled=$(gcloud services list --enabled | grep orgpolicy)
  sleep 5;
done

gcloud org-policies reset constraints/iam.disableServiceAccountKeyCreation --project=$PROJECT_ID | tee -a "$LOG"

echo "Waiting for policy change to get propagated...."  | tee -a "$LOG"
sleep 45

if gcloud iam service-accounts list --project $PROJECT_ID | grep -q $SA_NAME; then
  echo "Service account $SA_NAME has been found." | tee -a "$LOG"
else
  echo "Creating Service Account ... "  | tee -a "$LOG"
  gcloud iam service-accounts create $SA_NAME \
          --description="Service Account for calling DocAI API and Document Warehouse API" \
          --display-name="docai-utility-sa"  | tee -a "$LOG"
fi

gcloud services enable "documentai.googleapis.com" --project $DOCAI_WH_PROJECT_ID
if [ -f "$KEY_PATH" ] && [ -s "$KEY_PATH" ]; then
  echo "Key  ${KEY_PATH}  already exists locally, skipping" | tee -a "$LOG"
else
  echo "Generating and Downloading Service Account key into ${KEY_PATH}"  | tee -a "$LOG"
  gcloud iam service-accounts keys create "${KEY_PATH}"  --iam-account=${SA_EMAIL} | tee -a "$LOG"
fi



echo "Assigning required roles to ${SA_EMAIL}" | tee -a "$LOG"
gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="roles/logging.logWriter" | tee -a "$LOG"

gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="roles/storage.objectViewer" | tee -a "$LOG"

gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="roles/serviceusage.serviceUsageConsumer" | tee -a "$LOG"



echo "Creating DocAI output bucket  ${DOCAI_OUTPUT_BUCKET}" | tee -a "$LOG"
gsutil ls "gs://${DOCAI_OUTPUT_BUCKET}" 2> /dev/null
RETURN=$?
if [[ $RETURN -gt 0 ]]; then
    echo "Bucket does not exist, creating gs://${DOCAI_OUTPUT_BUCKET}" | tee -a "$LOG"
    gsutil mb gs://"$DOCAI_OUTPUT_BUCKET" | tee -a "$LOG"
    gcloud storage buckets add-iam-policy-binding  gs://"$DOCAI_OUTPUT_BUCKET" --member="serviceAccount:${SA_EMAIL}" --role="roles/storage.admin" | tee -a "$LOG"
fi

echo "Adding required roles/permissions for ${SA_EMAIL} " | tee -a "$LOG"
gcloud projects add-iam-policy-binding $DOCAI_WH_PROJECT_ID --member="serviceAccount:${SA_EMAIL}"  --role="roles/documentai.apiUser" | tee -a "$LOG"
gcloud projects add-iam-policy-binding $DOCAI_WH_PROJECT_ID --member="serviceAccount:${SA_EMAIL}"  --role="roles/contentwarehouse.documentAdmin"  | tee -a "$LOG"
gcloud projects add-iam-policy-binding $DOCAI_WH_PROJECT_ID --member="serviceAccount:${SA_EMAIL}"  --role="roles/contentwarehouse.admin"  | tee -a "$LOG"
gcloud projects add-iam-policy-binding $DOCAI_WH_PROJECT_ID --member="serviceAccount:${SA_EMAIL}"  --role="roles/documentai.viewer"  | tee -a "$LOG"

# Give Access to DocAI service account to access input bucket
if [ "$DATA_PROJECT_ID" != "$DOCAI_WH_PROJECT_ID" ]; then
    gcloud projects add-iam-policy-binding "$DATA_PROJECT_ID" --member="serviceAccount:${SA_EMAIL}"  --role="roles/storage.objectViewer"  | tee -a "$LOG"
    gcloud projects add-iam-policy-binding "$DATA_PROJECT_ID" --member="serviceAccount:${SA_DOCAI}"  --role="roles/storage.objectViewer" | tee -a "$LOG"
    gcloud projects add-iam-policy-binding "$DATA_PROJECT_ID" --member="serviceAccount:${SA_DOCAI_WH}"  --role="roles/storage.objectViewer" | tee -a "$LOG"
fi

if [ "$DATA_PROJECT_ID" != "$DOCAI_PROJECT_ID" ]; then
    gcloud projects add-iam-policy-binding "$DATA_PROJECT_ID" --member="serviceAccount:${SA_DOCAI}"  --role="roles/storage.objectViewer" | tee -a "$LOG"
fi

if [ "$DOCAI_PROJECT_ID" != "$DOCAI_WH_PROJECT_ID" ]; then
  gcloud projects add-iam-policy-binding $DOCAI_PROJECT_ID --member="serviceAccount:${SA_EMAIL}"  --role="roles/documentai.viewer"  2>&1 | tee -a "$LOG"
  gcloud projects add-iam-policy-binding $DOCAI_PROJECT_ID --member="serviceAccount:${SA_EMAIL}"  --role="roles/documentai.apiUser"  2>&1 | tee -a "$LOG"
  gcloud projects add-iam-policy-binding "$DOCAI_WH_PROJECT_ID" --member="serviceAccount:${SA_DOCAI}"  --role="roles/storage.admin" | tee -a "$LOG"
fi

timestamp=$(date +"%m-%d-%Y_%H:%M:%S")

if [ -f "$KEY_PATH" ] && [ -s "$KEY_PATH" ]; then
  :
else
  echo "ERROR: Could not generate Service Account key $KEY_PATH for ${SA_EMAIL}. Maybe, Maximum count of generated keys reached? please, fix the issue and re-run the script"
fi

echo "$timestamp Finished. Saved Log into $LOG"  | tee -a "$LOG"