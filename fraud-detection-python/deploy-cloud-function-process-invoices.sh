#! /bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"


source "${DIR}/.env.local"

gcloud functions deploy process-invoices \
--region=${CLOUD_FUNCTION_LOCATION} \
--entry-point=process_invoice \
--runtime=python37 \
--service-account=${PROJECT_ID}@appspot.gserviceaccount.com \
--source=cloud-functions/process-invoices \
--timeout=400 \
--env-vars-file=cloud-functions/process-invoices/.env.yaml \
--trigger-resource=gs://${PROJECT_ID}-input-invoices \
--trigger-event=google.storage.object.finalize
