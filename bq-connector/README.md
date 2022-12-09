# Document AI BigQuery Connector

## Overview
The DocAI BQ Connector is a helper library that invokes the DocAI processing library, and formats the response for saving directly into BigQuery. The implementation should work on any processor that returns entities. Support for form processors has not been verified.

## Parsing Methodologies
There are currently two parsing methodologies supported. The parsing methodology is supplied via argument --parsing_methodology.

- entities: The entities in the response from DocAI will be iterated and the content field will be extracted and cast based on the supplied BQ table schema. The result will form a json dictionary for insert into BQ.
- normalized_values: The entities in the response will be iterated, and the normalized_value property will be used depending on the field type correpsonding to the column in the correpsonding BQ table schema.

## Setup
```commandline
pip install -r ./docai_bq_connector/requirements.txt
```

## Usage
```shell
usage: main.py [-h] [--bucket_name BUCKET_NAME] [--file_name FILE_NAME] 
			    [--content_type CONTENT_TYPE]
          [--processing_type_override {sync,async}]
          [--processor_project_id PROCESSOR_PROJECT_ID] 
			    [--processor_location PROCESSOR_LOCATION]
			    [--processor_id PROCESSOR_ID]
          [--async_output_folder ASYNC_OUTPUT_FOLDER]
			    [--max_sync_page_count MAX_SYNC_PAGE_COUNT]
			    [--write_extraction_result]
          [--extraction_output_bucket EXTRACTION_OUTPUT_BUCKET]
			    [--custom_fields CUSTOM_FIELDS]\
			    [--metadata_mapping_info METADATA_MAPPING_INFO]
          [--should_async_wait SHOULD_ASYNC_WAIT]
			    [--operation_id OPERATION_ID]
			    [--parsing_methodology {entities,normalized_values}]
          [--doc_ai_sync_timeout DOC_AI_SYNC_TIMEOUT | --doc_ai_async_timeout DOC_AI_ASYNC_TIMEOUT]
          [--destination_project_id DESTINATION_PROJECT_ID]
			    [--destination_dataset_id DESTINATION_DATASET_ID]
          [--destination_table_id DESTINATION_TABLE_ID]
			    [--include_raw_entities]
			    [--include_error_fields]
          [--retry_count RETRY_COUNT]
          [--continue_on_error] 
			    [--log {notset,debug,info,warning,error,critical}] [-q] [-v]

Document AI BQ Connector process input arguments

optional arguments:
  -h, --help            show this help message and exit
  --retry_count RETRY_COUNT
                        The retry attempt count if continue_on_error is True. Default is 1. If there are no retries, a final insert attempt will still
                        be made excluding the parsed document fields
  --continue_on_error   Indicates if processing should continue upon errors
  --log {notset,debug,info,warning,error,critical}
                        The default logging level.
  -q, --quiet           Suppress message output to console.
  -v, --version         show program's version number and exit

document arguments:
  --bucket_name BUCKET_NAME
                        The Google Cloud Storage bucket name for the source document. Example: 'split-docs'
  --file_name FILE_NAME
                        The file name for the source document within the bucket. Example: 'my-document-12.pdf'
  --content_type CONTENT_TYPE
                        The MIME type of the document to be processed
  --processing_type_override {sync,async}
                        If specified, overrides the default async/sync processing logic
  --processor_project_id PROCESSOR_PROJECT_ID
                        The project id for the processor to be used
  --processor_location PROCESSOR_LOCATION
                        The location of the processor to be used
  --processor_id PROCESSOR_ID
                        The id of the processor to be used
  --async_output_folder ASYNC_OUTPUT_FOLDER
  --max_sync_page_count MAX_SYNC_PAGE_COUNT
                        The maximum number of pages that will be supported for sync processing. If page count is larger, async processing will be used.
  --write_extraction_result
                        Indicates if raw results of extraction should be written to GCS
  --extraction_output_bucket EXTRACTION_OUTPUT_BUCKET
  --custom_fields CUSTOM_FIELDS
                        Custom field json dictionary to union with the resulting dictionary for BigQuery. Example: '{"event_id": 1, "document_type":
                        "my_document"}'
  --metadata_mapping_info METADATA_MAPPING_INFO
                        Json object holding information on how to map document metadata to BigQuery. If column name or value not provided, defaults
                        will be used if possible. Example: '{"file_name": {"bq_column_name": "doc_file_name", "metadata_value": "my_file.pdf",
                        "skip_map": "false" }'
  --should_async_wait SHOULD_ASYNC_WAIT
                        Specifies if the CLI should block and wait until async document operation is completed and process result into BigQuery
  --operation_id OPERATION_ID
                        An existing operation id for which to complete BQ processing
  --parsing_methodology {entities,normalized_values}
                        The parsing methodology
  --doc_ai_sync_timeout DOC_AI_SYNC_TIMEOUT
                        The sync processor timeout
  --doc_ai_async_timeout DOC_AI_ASYNC_TIMEOUT
                        The async processor timeout

bigquery arguments:
  --destination_project_id DESTINATION_PROJECT_ID
                        The BigQuery project id for the destination
  --destination_dataset_id DESTINATION_DATASET_ID
                        The BigQuery dataset id for the destination
  --destination_table_id DESTINATION_TABLE_ID
                        The BigQuery table id for the destination
  --include_raw_entities
                        If raw_entities field should be outputted to the specified table
  --include_error_fields
                        If 'has_errors' and 'errors' fields should be outputted to the specified table
```