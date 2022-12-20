bq --project_id=$PROJECT_ID \
   --dataset_id=$SUBMISSION_HUB_DATASET_ID \
   mk --table \
    --description="Used by docai_bq_connector to keep track of documents processed and to match up results of HITL reviews back to the original document" \
    --schema="./setup/doc_reference_table_schema" \
    doc_reference2
    