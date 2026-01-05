#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

source "${DIR}/.env.local"

gcloud storage buckets create --project=${PROJECT_ID} --default-storage-class=standard --location=${BUCKET_LOCATION} --uniform-bucket-level-access gs://${PROJECT_ID}-input-invoices
