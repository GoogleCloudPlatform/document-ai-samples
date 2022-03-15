
#! /bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

source "${DIR}/.env.local"

gsutil mb -p ${PROJECT_ID} -c standard -l ${BUCKET_LOCATION} -b on gs://${PROJECT_ID}-input-invoices
