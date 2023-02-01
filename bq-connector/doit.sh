#! /bin/bash
# A sample example of calling main.py function, to process PDF form and store raw_entities as is in BQ

# Developer replace data below below (at least PROCESSOR_ID, FILE_NAME)
PROCESSOR_PROJECT_ID="${PROJECT_ID}"    # The project id for the processor to be used
PROCESSOR_ID="_processor_id_"           # The id of the processor to be used  BSC
BUCKET_NAME="${PROJECT_ID}"             # The Google Cloud Storage bucket name for the source document. Example: 'split-docs'
FILE_NAME="path/to/form.pdf"            # The file name for the source document within the bucket. Example: 'my-document-12.pdf'
DESTINATION_PROJECT_ID=${PROJECT_ID}    # The BigQuery project id for the destination
DESTINATION_DATASET_ID="${DATASET_ID}"   # The BigQuery dataset id for the destination
DESTINATION_TABLE_ID="doc_reference"     # The BigQuery table id for the destination

CONTENT_TYPE="application/pdf"          # The MIME type of the document to be processed
PROCESSOR_LOCATION="us"                 # The location of the processor to be used
PARSING_METHODOLOGY="entities"          # entities,form,normalized_values   default="entities"
EXTRACTION_OUTPUT_BUCKET="${PROJECT_ID}-docai-output"
ASYNC_OUTPUT_FOLDER_GCS_URI="gs://${PROJECT_ID}-docai-output"


echo "--bucket_name $BUCKET_NAME
          --file_name $FILE_NAME
          --content_type $CONTENT_TYPE
          --processor_project_id $PROCESSOR_PROJECT_ID
          --processor_location $PROCESSOR_LOCATION
          --processor_id $PROCESSOR_ID
          --extraction_output_bucket $EXTRACTION_OUTPUT_BUCKET
          --parsing_methodology $PARSING_METHODOLOGY
          --destination_project_id $DESTINATION_PROJECT_ID
          --destination_dataset_id $DESTINATION_DATASET_ID
          --destination_table_id $DESTINATION_TABLE_ID
          --async_output_folder_gcs_uri $ASYNC_OUTPUT_FOLDER_GCS_URI
          --include_raw_entities"

python main.py \
  --bucket_name $BUCKET_NAME \
  --file_name $FILE_NAME \
  --content_type $CONTENT_TYPE \
  --processor_project_id $PROCESSOR_PROJECT_ID \
  --processor_location $PROCESSOR_LOCATION \
  --processor_id $PROCESSOR_ID \
  --extraction_output_bucket $EXTRACTION_OUTPUT_BUCKET \
  --parsing_methodology $PARSING_METHODOLOGY \
  --destination_project_id $DESTINATION_PROJECT_ID \
  --destination_dataset_id $DESTINATION_DATASET_ID \
  --destination_table_id $DESTINATION_TABLE_ID \
  --async_output_folder_gcs_uri $ASYNC_OUTPUT_FOLDER_GCS_URI \
  --include_raw_entities

