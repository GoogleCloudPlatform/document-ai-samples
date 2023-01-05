#!/bin/bash
bq --project_id=$PROJECT_ID \
   --dataset_id=$DATASET_ID \
   mk --table \
    --description="Used by docai_bq_connector to keep track of documents processed and to match up results of HITL reviews back to the original document" \
    --schema="./setup/doc_reference_table_schema.json" \
    doc_reference
    