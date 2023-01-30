#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
bq mk \
  --table \
  --project_id=$PROJECT_ID \
  --dataset_id=$DATASET_ID \
  --description="Used by docai_bq_connector to keep track of documents processed and to match up results of HITL reviews back to the original document" \
  --schema="$DIR/doc_reference_table_schema.json" \
  "$DATASET_ID.doc_reference"