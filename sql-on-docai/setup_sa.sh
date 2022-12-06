#!/bin/bash

#####################################################################################################
# Script Name: setup_sa.sh
# Date of Creation: 12/01/2022
# Author: Ankur Wahi
# Updated: 12/01/2022
#####################################################################################################



source ./config.sh
gcloud auth login ${USER_EMAIL}
echo "Assigning IAM Permissions"
gcloud config set project ${PROJECT_ID}

##################################################
##
## Enable APIs
##
##################################################

echo "enabling the necessary APIs"

gcloud services enable compute.googleapis.com

gcloud services enable storage.googleapis.com

gcloud services enable bigquery.googleapis.com

gcloud services enable bigqueryconnection.googleapis.com

gcloud services enable cloudfunctions.googleapis.com

gcloud services enable artifactregistry.googleapis.com

gcloud services enable run.googleapis.com

gcloud services enable cloudbuild.googleapis.com

gcloud services enable cloudresourcemanager.googleapis.com

gcloud services enable documentai.googleapis.com


PROJECT_NUMBER=$(gcloud projects list --filter="project_id:${PROJECT_ID}"  --format='value(project_number)')



SERVICE_ACCOUNT=${PROJECT_NUMBER}-compute@developer.gserviceaccount.com 
echo "Compute engine SA - ${SERVICE_ACCOUNT}"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member=serviceAccount:${SERVICE_ACCOUNT} \
    --role=roles/serviceusage.serviceUsageAdmin
    
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member=serviceAccount:${SERVICE_ACCOUNT} \
    --role=roles/storage.admin
    
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member=serviceAccount:${SERVICE_ACCOUNT} \
    --role=roles/documentai.admin


sleep 15



# Cloud function setup for EE

project_id=${PROJECT_ID}

doc_sa=${SERVICE_ACCOUNT}

echo "Doc AI SA: ${doc_sa}"


#Create the external connection for BQ

bq mk --connection --display_name='my_gcf-docai-conn' \
      --connection_type=CLOUD_RESOURCE \
      --project_id=$(gcloud config get-value project) \
      --location=US  gcf-docai-conn

#Get serviceAccountID associated with the connection  

serviceAccountId=`bq show --location=US --connection --format=json gcf-docai-conn| jq -r '.cloudResource.serviceAccountId'`
echo "Service Account: ${serviceAccountId}"

# Add Cloud run admin
gcloud projects add-iam-policy-binding \
$(gcloud config get-value project) \
--member='serviceAccount:'${serviceAccountId} \
--role='roles/run.admin'

gcloud projects add-iam-policy-binding \
$(gcloud config get-value project) \
--member='serviceAccount:'${serviceAccountId} \
--role='roles/storage.objectViewer'

echo "export doc_sa=${doc_sa}" >> ~/docai-on-bigquery/config.sh
