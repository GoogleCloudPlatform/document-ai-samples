#
# Copyright 2022 Google LLC
#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import argparse
import json
import logging
import os

from docai_bq_connector import DocAIBQConnector,BqMetadataMappingInfo

script_dir = os.path.dirname(__file__)


def main():
    arg_parser = argparse.ArgumentParser(description='Document AI BQ Connector process input arguments',
                                         allow_abbrev=False)

    doc_options_group = arg_parser.add_argument_group('document arguments')
    doc_options_group.add_argument('--bucket_name', type=str, help='The Google Cloud Storage bucket name for the '
                                                                   'source document. Example: \'split-docs\'')
    doc_options_group.add_argument('--file_name', type=str,
                                   help='The file name for the source document within the bucket. Example: '
                                        '\'my-document-12.pdf\'')
    doc_options_group.add_argument('--content_type', type=str, help='The MIME type of the document to be processed')
    doc_options_group.add_argument('--processing_type_override', choices=['sync', 'async'],
                                   default=None,
                                   help='If specified, overrides the default async/sync processing logic')
    doc_options_group.add_argument('--processor_project_id', type=str,
                                   help='The project id for the processor to be used')
    doc_options_group.add_argument('--processor_location', type=str, help='The location of the processor to be used')
    doc_options_group.add_argument('--processor_id', type=str, help='The id of the processor to be used')
    doc_options_group.add_argument('--async_output_folder', type=str, default="output", help='')
    doc_options_group.add_argument('--max_sync_page_count', type=int, default=5, help='The maximum number of pages '
                                                                                      'that will be supported for '
                                                                                      'sync processing. If page count '
                                                                                      'is larger, async processing '
                                                                                      'will be used.')
    doc_options_group.add_argument('--write_extraction_result', action='store_true', help='Indicates if raw results of '
                                                                                          'extraction should be '
                                                                                          'written '
                                                                                          'to GCS')
    doc_options_group.add_argument('--extraction_output_bucket', type=str, help='')
    doc_options_group.add_argument('--custom_fields', type=json.loads, help='Custom field json dictionary to union '
                                                                            'with the '
                                                                            'resulting dictionary for BigQuery. '
                                                                            'Example: \'{"event_id": 1, '
                                                                            '"document_type": "my_document"}\'')
    doc_options_group.add_argument('--metadata_mapping_info', type=json.loads, help='Json object holding information on how to map document '
                                                                             'metadata to BigQuery. If column name or value not provided, '
                                                                             'defaults will be used if possible. '
                                                                             'Example: \'{"file_name": {"bq_column_name": "doc_file_name", '
                                                                                        '               "metadata_value": "my_file.pdf", '
                                                                                        '               "skip_map": "false"  }\'')  
    doc_options_group.add_argument('--should_async_wait', type=bool, default=True, help='Specifies if the CLI should '
                                                                                        'block and wait until async '
                                                                                        'document operation is '
                                                                                        'completed and process result '
                                                                                        'into BigQuery')
    doc_options_group.add_argument('--operation_id', type=str, help='An existing operation id for which to complete '
                                                                    'BQ processing')
    doc_options_group.add_argument('--parsing_methodology', choices=['entities', 'normalized_values'],
                                   default='entities',
                                   help='The parsing methodology')

    timeout_filter_group = doc_options_group.add_mutually_exclusive_group()
    timeout_filter_group.add_argument('--doc_ai_sync_timeout', type=int, default=900, help='The sync processor timeout')
    timeout_filter_group.add_argument('--doc_ai_async_timeout', type=int, default=900,
                                      help='The async processor timeout')

    bigquery_options_group = arg_parser.add_argument_group('bigquery arguments')
    bigquery_options_group.add_argument('--destination_project_id', help='The BigQuery project id for the destination')
    bigquery_options_group.add_argument('--destination_dataset_id', help='The BigQuery dataset id for the destination')
    bigquery_options_group.add_argument('--destination_table_id', help='The BigQuery table id for the destination')
    bigquery_options_group.add_argument('--include_raw_entities', action='store_true',
                                        help='If raw_entities field should be outputted to the specified table')
    bigquery_options_group.add_argument('--include_error_fields', action='store_true',
                                        help='If \'has_errors\' and \'errors\' fields should be outputted to the '
                                             'specified table')

    arg_parser.add_argument('--retry_count', type=int, default=1, help='The retry attempt count if continue_on_error '
                                                                       'is True. Default is 1. If '
                                                                       'there are no retries, a final insert attempt '
                                                                       'will still be made excluding the parsed '
                                                                       'document fields')
    arg_parser.add_argument('--continue_on_error', action='store_true', help='Indicates if processing should continue '
                                                                             'upon errors')
    arg_parser.add_argument('--log', choices=['notset', 'debug', 'info', 'warning', 'error', 'critical'],
                            default='info',
                            help='The default logging level.')
    arg_parser.add_argument('-q', '--quiet', action='store_true', help='Suppress message output to console.')
    arg_parser.add_argument('-v', '--version', action='version', version='Document AI BQ Connector 1.0.0')

    args = arg_parser.parse_args()

    logging.basicConfig(level=args.log.upper())
    logging.debug(args)

    bucket_name = args.bucket_name
    file_name = args.file_name
    content_type = args.content_type
    processing_type_override = args.processing_type_override
    processor_project_id = args.processor_project_id
    processor_location = args.processor_location
    processor_id = args.processor_id
    async_output_folder = args.async_output_folder
    should_async_wait = args.should_async_wait
    should_write_extraction_result = args.write_extraction_result
    extraction_result_output_bucket = args.extraction_output_bucket
    operation_id = args.operation_id
    doc_ai_sync_timeout = args.doc_ai_sync_timeout
    doc_ai_async_timeout = args.doc_ai_async_timeout
    destination_project_id = args.destination_project_id
    destination_dataset_id = args.destination_dataset_id
    destination_table_id = args.destination_table_id
    include_raw_entities = args.include_raw_entities
    include_error_fields = args.include_error_fields
    retry_count = args.retry_count
    continue_on_error = args.continue_on_error
    custom_fields = args.custom_fields
    max_sync_page_count = args.max_sync_page_count
    parsing_methodology = args.parsing_methodology

    my_metadata_mapping_info = None
    if args.metadata_mapping_info is not None:
        my_metadata_mapping_info = {}
        for cur_metadata_name, cur_metadata_mapping_info in args.metadata_mapping_info.items():
            my_metadata_mapping_info[cur_metadata_name] = BqMetadataMappingInfo(bq_column_name = cur_metadata_mapping_info.get('bq_column_name'),
                                                                             metadata_value = cur_metadata_mapping_info.get('metadata_value'), skip_map = cur_metadata_mapping_info.get('skip_map')
                                                                            )
    
    connector = DocAIBQConnector(
        bucket_name=bucket_name,
        file_name=file_name,
        content_type=content_type,
        processing_type_override=processing_type_override,
        processor_project_id=processor_project_id,
        processor_location=processor_location,
        processor_id=processor_id,
        async_output_folder=async_output_folder,
        should_async_wait=should_async_wait,
        extraction_result_output_bucket=extraction_result_output_bucket,
        should_write_extraction_result=should_write_extraction_result,
        operation_id=operation_id,
        destination_project_id=destination_project_id,
        destination_dataset_id=destination_dataset_id,
        destination_table_id=destination_table_id,
        doc_ai_sync_timeout=doc_ai_sync_timeout,
        doc_ai_async_timeout=doc_ai_async_timeout,
        custom_fields=custom_fields,
        metadata_mapping_info=my_metadata_mapping_info,
        include_raw_entities=include_raw_entities,
        include_error_fields=include_error_fields,
        retry_count=retry_count,
        continue_on_error=continue_on_error,
        max_sync_page_count=max_sync_page_count,
        parsing_methodology=parsing_methodology
    )

    connector.run()


if __name__ == "__main__":
    main()
