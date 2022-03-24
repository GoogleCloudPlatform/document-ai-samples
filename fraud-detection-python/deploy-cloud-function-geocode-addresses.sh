#! /bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

source "${DIR}/.env.local"

gcloud functions deploy geocode-addresses \
--region=${CLOUD_FUNCTION_LOCATION} \
--entry-point=process_address \
--runtime=python38 \
--service-account=${PROJECT_ID}@appspot.gserviceaccount.com \
--source=cloud-functions/geocode-addresses \
--timeout=60 \
--env-vars-file=cloud-functions/geocode-addresses/.env.yaml \
--trigger-topic=${GEO_CODE_REQUEST_PUBSUB_TOPIC}
