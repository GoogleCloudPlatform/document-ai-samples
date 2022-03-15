#! /bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

source "${DIR}/.env.local"

bq --location=US mk  -d \
--description "Invoice Parser Results" \
${PROJECT_ID}:invoice_parser_results

bq mk --table invoice_parser_results.doc_ai_extracted_entities table-schema/doc_ai_extracted_entities.json

bq mk --table invoice_parser_results.geocode_details table-schema/geocode_details.json