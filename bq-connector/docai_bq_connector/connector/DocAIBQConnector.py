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

import logging
import uuid
from typing import Dict

from docai_bq_connector.bigquery.StorageManager import StorageManager
from docai_bq_connector.connector.BqDocumentMapper import BqDocumentMapper
from docai_bq_connector.connector.BqMetadataMapper import BqMetadataMapper, BqMetadataMappingInfo
from docai_bq_connector.doc_ai_processing.Processor import Processor
from docai_bq_connector.doc_ai_processing.DocumentOperation import DocumentOperation
from docai_bq_connector.exception.TableNotFoundError import TableNotFoundError


class DocAIBQConnector:
    def __init__(
        self,
        bucket_name: str,
        file_name: str,
        content_type: str,
        processing_type_override: str,
        processor_project_id: str,
        processor_location: str,
        processor_id: str,
        async_output_folder: str,
        should_async_wait: bool,
        operation_id: str,
        destination_project_id: str,
        destination_dataset_id: str,
        destination_table_id: str,
        doc_ai_sync_timeout: int = 900,
        doc_ai_async_timeout: int = 900,
        extraction_result_output_bucket: str = None,
        custom_fields: dict = None,
        metadata_mapping_info: Dict[str, BqMetadataMappingInfo] = None,
        include_raw_entities: bool = True,
        include_error_fields: bool = True,
        retry_count: int = 1,
        continue_on_error: bool = False,
        should_write_extraction_result: bool = True,
        max_sync_page_count: int = 5,
        parsing_methodology: str = 'entities'
    ):
        self.bucket_name = bucket_name
        self.file_name = file_name
        self.content_type = content_type
        self.processing_type_override = processing_type_override
        self.processor_project_id = processor_project_id
        self.processor_location = processor_location
        self.processor_id = processor_id
        self.async_output_folder = async_output_folder
        self.should_async_wait = should_async_wait
        self.operation_id = operation_id
        self.destination_project_id = destination_project_id
        self.destination_dataset_id = destination_dataset_id
        self.destination_table_id = destination_table_id
        self.doc_ai_sync_timeout = doc_ai_sync_timeout
        self.doc_ai_async_timeout = doc_ai_async_timeout
        self.extraction_result_output_bucket = extraction_result_output_bucket
        self.custom_fields = custom_fields
        self.metadata_mapper = BqMetadataMapper(metadata_mapping_info)
        self.include_raw_entities = include_raw_entities
        self.include_error_fields = include_error_fields
        self.retry_count = retry_count
        self.continue_on_error = continue_on_error
        self.should_write_extraction_result = should_write_extraction_result
        self.max_sync_page_count = max_sync_page_count
        self.parsing_methodology = parsing_methodology

    def run(self):
        # Check if was invoked for a new document, or for an existing operation.
        if self.operation_id is None:
            # New document
            # 1. Process document by instantiating and calling process() on the document processor class.
            # 2. Process result, validate types, convert as necessary and store in destination BQ table.
            doc_ai_process = Processor(
                bucket_name=self.bucket_name,
                file_name=self.file_name,
                content_type=self.content_type,
                processor_project_id=self.processor_project_id,
                processor_location=self.processor_location,
                processor_id=self.processor_id,
                extraction_result_output_bucket=self.extraction_result_output_bucket,
                async_output_folder=self.async_output_folder,
                sync_timeout=self.doc_ai_sync_timeout,
                async_timeout=self.doc_ai_async_timeout,
                should_async_wait=self.should_async_wait,
                should_write_extraction_result=self.should_write_extraction_result,
                max_sync_page_count=self.max_sync_page_count
            )

            document = doc_ai_process.process()

            storage_manager = StorageManager(
                self.destination_project_id, self.destination_dataset_id
            )
            if storage_manager.does_table_exist(self.destination_table_id):
                schema = storage_manager.get_table_schema(self.destination_table_id)
                
                _hitl_op_id = None
                if isinstance(document, DocumentOperation) and document is not None:
                    _hitl_op_id = document.operation_id

                self._augment_metadata_mapping_info(file_name = self.file_name, hitl_operation_id = _hitl_op_id)    

                mapper = BqDocumentMapper(
                    document=document,
                    bq_schema=schema,
                    metadata_mapper=self.metadata_mapper,
                    custom_fields=self.custom_fields,
                    include_raw_entities=self.include_raw_entities,
                    include_error_fields=self.include_error_fields,
                    parsing_methodology=self.parsing_methodology
                )

                if (
                    self.continue_on_error is False
                    and self.include_error_fields is False
                    and len(mapper.errors) > 0
                ):
                    logging.error(mapper.errors)
                    exit(100)
                bq_row = mapper.to_bq_row()

                # 1: Attempt initial row insert
                insert_1_errors = storage_manager.write_record(
                    self.destination_table_id, bq_row
                )
                self.log_bq_errors(1, insert_1_errors)
                exclude_fields: [str] = mapper.process_insert_errors(insert_1_errors)

                retry_success = False
                if self.continue_on_error is True:
                    # 2: Attempt a second insert removing the offending fields
                    if len(insert_1_errors) > 0 and len(exclude_fields) > 0:
                        current_try = 0
                        while current_try < self.retry_count:
                            current_try += 1
                            # BQ only reports a single column insert error per row
                            bq_row_attempt_2 = mapper.to_bq_row(
                                exclude_fields=exclude_fields
                            )
                            insert_2_errors = storage_manager.write_record(
                                self.destination_table_id, bq_row_attempt_2
                            )
                            self.log_bq_errors(current_try, insert_2_errors)
                            exclude_fields.extend(
                                mapper.process_insert_errors(insert_2_errors)
                            )
                            if len(insert_2_errors) == 0:
                                retry_success = True
                                break

                    # 3: If fails again, then fallback excluding the entities
                    if len(insert_1_errors) > 0 and retry_success is False:
                        bq_row_attempt_3 = mapper.to_bq_row(append_parsed_fields=False)
                        if len(bq_row_attempt_3) > 0:
                            insert_3_errors = storage_manager.write_record(
                                self.destination_table_id, bq_row_attempt_3
                            )
                            self.log_bq_errors(self.retry_count + 1, insert_3_errors)
                        else:
                            logging.warning("There are no fields to insert")
            else:
                raise TableNotFoundError(
                    f"Destination table {self.destination_table_id} not found "
                    f"in '{self.destination_project_id}.{self.destination_dataset_id}'"
                )
        else:
            # TODO: Get result, process result, validate types, convert as necessary and store in destination BQ table.
            pass

    @staticmethod
    def log_bq_errors(retry, errors):
        if errors:
            logging.warning(
                "BQ submission insert errors from attempt %s: %s", retry, errors
            )
        else:
            logging.info("BQ submission insert attempt %s succeeded", retry)

    # Augment the configured metadata mapping info with default values that could be populated
    def _augment_metadata_mapping_info(self, file_name, hitl_operation_id):
        if self.metadata_mapper is None:
            return
        else:
            self.metadata_mapper.set_default_value_for_metadata_if_not_set("file_name",file_name)
            self.metadata_mapper.set_default_value_for_metadata_if_not_set("doc_event_id", str(uuid.uuid4()))
            self.metadata_mapper.set_default_value_for_metadata_if_not_set("hitl_operation_id",hitl_operation_id)
