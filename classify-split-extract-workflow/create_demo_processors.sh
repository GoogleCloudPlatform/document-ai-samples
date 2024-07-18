#!/bin/bash

# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "${DIR}/vars.sh"
LOCATION="us"

function create_processor() {
  name="$1"
  type="$2"
  echo "Creating processor $name with type $type"
  response=$(curl -X POST \
    -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    -H "Content-Type: application/json; charset=utf-8" \
    -d "{\"displayName\": \"$name\", \"type\": \"$type\"}" \
    "https://$LOCATION-documentai.googleapis.com/v1/projects/$PROJECT_ID/locations/$LOCATION/processors")

  processor_name=$(echo "$response" | jq -r '.name')
  echo "Processor created: $processor_name"

  # Correctly update the processor_id within the relevant parser object
  jq --arg name "$processor_name" '.parser_config.'"${name}"'.processor_id = $name' "$DIR/classify-job/config/config.json" > temp.json && mv temp.json "$DIR/classify-job/config/config.json"
}

create_processor ocr_parser OCR_PROCESSOR
create_processor int1099_parser FORM_1099INT_PROCESSOR
create_processor misc1099_parser FORM_1099MISC_PROCESSOR
create_processor w2_parser FORM_W2_PROCESSOR
create_processor classifier LENDING_DOCUMENT_SPLIT_PROCESSOR