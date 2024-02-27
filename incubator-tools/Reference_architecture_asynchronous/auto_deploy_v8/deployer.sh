#!/bin/bash
# shellcheck disable=SC2129

source input.sh

# Prompt user for project and function names
#read -p "Enter the project name: " PROJECT_NAME
#read -p "Enter the function name: " FUNCTION_NAME
#read -p "Enter the location: " LOCATION
#read -p "Enter the runtime: " RUNTIME
#read -p "Enter the GCS bucket name: " BUCKET_NAME
#read -p "Enter the Service Account name: " SERVICE_ACCOUNT_NAME
#read -p "Enter the script name: " SCRIPT_NAME
#read -p "Enter the Scheduler name: " SCHEDULER_NAME
#read -p "Enter the Processor name: " PROCESSOR_NAME

# Truncate the file each run
: >config.txt

echo 'PROJECT_NAME : ' $PROJECT_NAME &>>config.txt
echo 'FUNCTION_NAME : ' $FUNCTION_NAME &>>config.txt
echo 'LOCATION : ' $LOCATION &>>config.txt
echo 'BUCKET_NAME : ' $BUCKET_NAME &>>config.txt
echo 'SERVICE_ACCOUNT_NAME : ' $SERVICE_ACCOUNT_NAME &>>config.txt
echo 'SCHEDULER_NAME : ' $SCHEDULER_NAME &>>config.txt

# Check if the project exists  | Works!
if gcloud projects describe $PROJECT_NAME &>/dev/null; then
	echo "Project already exists."
	gcloud config set project $PROJECT_NAME
else
	echo "Project doesn't exists. Please use an exisiting project name"
fi

# Check if the Firestore database exists | Its there in script... no need to create!!!!
#if gcloud firestore describe-index --project $PROJECT_NAME &> /dev/null; then
#  echo "Firestore database already exists."
#else
# Create the Firestore database
#  gcloud firestore create-index --project $PROJECT_NAME --collection-group=''
#fi

# Check if the GCS bucket exists | Works!
if gsutil ls gs://$BUCKET_NAME &>/dev/null; then
	echo "Bucket already exists."
else
	# Create the GCS bucket
	gcloud storage buckets create gs://$BUCKET_NAME --project=$PROJECT_NAME --default-storage-class=STANDARD --location=$LOCATION --uniform-bucket-level-access
fi

# Move the input files ot input landing bucket
gsutil cp input_files/* gs://$BUCKET_NAME/

#https://g3doc.corp.google.com/cloud/ai/documentai/core/c/g3doc/infra_dev_guide/how_to_use_call_dai.md?cl=head#http-api
#Create Invoice Processor | jq will parse the JSON response get the 'name' attribute | PROCESSOR_DETAILS is a variable which holds 'name' attribute
PROCESSOR_DETAILS=$(curl -X POST -v -H "Authorization: Bearer $(gcloud auth application-default print-access-token)" -H "Content-Type: application/json" \
	https://us-documentai.googleapis.com/uiv1beta3/projects/$PROJECT_NAME/locations/us/processors \
	-d '{
  "type": "INVOICE_PROCESSOR",
  "display_name": "DAIRA_test_PROCESSOR",
}' | jq -r '.name')
echo "${PROCESSOR_DETAILS}"
echo 'PROCESSOR_DETAILS : ' $PROCESSOR_DETAILS &>>config.txt
echo "DAIRA_Test_PROCESSOR is created..."

#Move the generated config file to input landing page directory
gsutil cp config.txt gs://$BUCKET_NAME/config/

#SA: if its existing, use it. else create SA and use it
if gcloud iam service-accounts describe $SERVICE_ACCOUNT_NAME@$PROJECT_NAME.iam.gserviceaccount.com &>/dev/null; then
	echo "SA already exists."
	#gcloud config set account "$SERVICE_ACCOUNT_NAME@$PROJECT_NAME.iam.gserviceaccount.com"

else
	# create SA for cloud function to use | works!
	echo "SA DOESN'T exists. CREATING...."
	gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
		--display-name $SERVICE_ACCOUNT_NAME

	# only the admin can run | works!
	gcloud projects add-iam-policy-binding $PROJECT_NAME \
		--member "serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_NAME.iam.gserviceaccount.com" \
		--role "roles/cloudfunctions.developer"

	gcloud projects add-iam-policy-binding $PROJECT_NAME \
		--member "serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_NAME.iam.gserviceaccount.com" \
		--role "roles/run.invoker"

	gcloud projects add-iam-policy-binding $PROJECT_NAME \
		--member "serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_NAME.iam.gserviceaccount.com" \
		--role "roles/documentai.editor"

	gcloud projects add-iam-policy-binding $PROJECT_NAME \
		--member "serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_NAME.iam.gserviceaccount.com" \
		--role "roles/datastore.user"

	gcloud projects add-iam-policy-binding $PROJECT_NAME \
		--member "serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_NAME.iam.gserviceaccount.com" \
		--role "roles/storage.admin"

	gcloud projects add-iam-policy-binding $PROJECT_NAME \
		--member "serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_NAME.iam.gserviceaccount.com" \
		--role "roles/iam.serviceAccountUser"

	gcloud projects add-iam-policy-binding $PROJECT_NAME \
		--member "serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_NAME.iam.gserviceaccount.com" \
		--role "roles/iam.serviceAccountAdmin"
	#gcloud config set account "test-SA-incubator@rand-automl-project.iam.gserviceaccount.com"

fi

# Create and deploy to functions | works!

gcloud beta functions deploy $FUNCTION_NAME \
	--gen2 \
	--project=$PROJECT_NAME \
	--runtime=python310 \
	--region=us-central1 \
	--source=CFScript/ \
	--entry-point=hello_world \
	--memory=1Gi \
	--cpu=1000m \
	--concurrency=100 \
	--min-instances=1 \
	--max-instances=100 \
	--timeout=3600 \
	--service-account=$SERVICE_ACCOUNT_NAME@$PROJECT_NAME.iam.gserviceaccount.com \
	--trigger-http \
	--no-allow-unauthenticated
#--service-account=atulkumard-rand-automl-project@rand-automl-project.iam.gserviceaccount.com \

# Here you get the output url endpoint of the deployed cloud function gen2 | save it to some variable and reuse it for scheduler uri | Working
CF_URI_ENDPOINT=$(gcloud functions describe $FUNCTION_NAME \
	--gen2 \
	--region=us-central1 \
	--format="value(serviceConfig.uri)")

echo $CF_URI_ENDPOINT

# Check if the Cloud Scheduler job exists | Working
if gcloud scheduler jobs describe $SCHEDULER_NAME &>/dev/null; then
	echo "Cloud Scheduler job already exists."
else
	# Create the Cloud Scheduler job
	gcloud scheduler jobs create http $SCHEDULER_NAME \
		--project $PROJECT_NAME \
		--schedule "0 * * * *" \
		--oidc-service-account-email $SERVICE_ACCOUNT_NAME@$PROJECT_NAME.iam.gserviceaccount.com \
		--location us-west2 \
		--time-zone Asia/Calcutta \
		--uri "$CF_URI_ENDPOINT"
fi
