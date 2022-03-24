#! /bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

source "${DIR}/.env.local"

gcloud pubsub topics \
  create ${GEO_CODE_REQUEST_PUBSUB_TOPIC}
  
