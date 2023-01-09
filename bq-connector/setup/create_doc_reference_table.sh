#!/bin/bash
bq mk \
  --table \
  --project_id=$PROJECT_ID \
  --dataset_id=$DATASET_ID \
  --description="Used by docai_bq_connector to keep track of documents processed and to match up results of HITL reviews back to the original document" \
  --schema="./doc_reference_table_schema.json" \
  "$DATASET_ID.doc_reference"