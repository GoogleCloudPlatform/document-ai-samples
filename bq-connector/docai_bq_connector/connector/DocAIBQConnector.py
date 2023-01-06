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
from datetime import datetime
from typing import Dict, Optional

from docai_bq_connector.bigquery.StorageManager import StorageManager
from docai_bq_connector.connector.BqDocumentMapper import BqDocumentMapper
from docai_bq_connector.connector.BqMetadataMapper import (
    BqMetadataMapper,
    BqMetadataMappingInfo,
)
from docai_bq_connector.doc_ai_processing.DocumentState import DocumentState
from docai_bq_connector.doc_ai_processing.ProcessedDocument import ProcessedDocument
from docai_bq_connector.doc_ai_processing.Processor import Processor
from docai_bq_connector.exception.DocReferenceException import (
    InitialDocRecordNotFoundError,
    DocAlreadyProcessedError,
)
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
        async_output_folder_gcs_uri: str,
        should_async_wait: bool,
        operation_id: str,
        destination_project_id: str,
        destination_dataset_id: str,
        destination_table_id: str,
        doc_ai_sync_timeout: int = 900,
        doc_ai_async_timeout: int = 900,
        extraction_result_output_bucket: Optional[str] = None,
        custom_fields: Optional[dict] = None,
        metadata_mapping_info: Optional[Dict[str, BqMetadataMappingInfo]] = None,
        include_raw_entities: bool = True,
        include_error_fields: bool = True,
        retry_count: int = 1,
        continue_on_error: bool = False,
        should_write_extraction_result: bool = True,
        max_sync_page_count: int = 5,
        parsing_methodology: str = "entities",
    ):
        self.bucket_name = bucket_name
        self.file_name = file_name
        self.content_type = content_type
        self.processing_type_override = processing_type_override
        self.processor_project_id = processor_project_id
        self.processor_location = processor_location
        self.processor_id = processor_id
        self.async_output_folder_gcs_uri = async_output_folder_gcs_uri
        self.should_async_wait = should_async_wait
        self.operation_id = operation_id
        self.destination_project_id = destination_project_id
        self.destination_dataset_id = destination_dataset_id
        self.destination_table_id = destination_table_id
        self.doc_ai_sync_timeout = doc_ai_sync_timeout
        self.doc_ai_async_timeout = doc_ai_async_timeout
        self.extraction_result_output_bucket = extraction_result_output_bucket
        self.custom_fields = custom_fields
        self.metadata_mapper = BqMetadataMapper(
            metadata_mapping_info if metadata_mapping_info else {}
        )
        self.include_raw_entities = include_raw_entities
        self.include_error_fields = include_error_fields
        self.retry_count = retry_count
        self.continue_on_error = continue_on_error
        self.should_write_extraction_result = should_write_extraction_result
        self.max_sync_page_count = max_sync_page_count
        self.parsing_methodology = parsing_methodology

    def run(self):
        storage_manager = StorageManager(
            self.destination_project_id, self.destination_dataset_id
        )
        doc_ai_process = Processor(
            bucket_name=self.bucket_name,
            file_name=self.file_name,
            content_type=self.content_type,
            processor_project_id=self.processor_project_id,
            processor_location=self.processor_location,
            processor_id=self.processor_id,
            extraction_result_output_bucket=self.extraction_result_output_bucket,
            async_output_folder_gcs_uri=self.async_output_folder_gcs_uri,
            sync_timeout=self.doc_ai_sync_timeout,
            async_timeout=self.doc_ai_async_timeout,
            should_async_wait=self.should_async_wait,
            should_write_extraction_result=self.should_write_extraction_result,
            max_sync_page_count=self.max_sync_page_count,
        )

        document = doc_ai_process.process()

        # Check if it was invoked for a new document, or for an existing operation.
        if self.operation_id is None:
            # New document
            # Check if a HITL operation was initiated as part of the processing

            _hitl_op_id = None
            if isinstance(document, ProcessedDocument) and document is not None:
                _hitl_op_id = document.hitl_operation_id

            _current_doc_status = DocumentState.unknown
            if _hitl_op_id is None:
                _current_doc_status = DocumentState.document_processing_complete
            else:
                _current_doc_status = DocumentState.submitted_for_hitl

            _doc_unique_id = self._augment_metadata_mapping_info(
                file_name=self.file_name,
                hitl_operation_id=_hitl_op_id,
                doc_status=_current_doc_status,
            )

            # Insert tracking info in the doc_reference table
            bq_row = {
                "doc_id": _doc_unique_id,
                "file_name": self.file_name,
                "doc_status": str(_current_doc_status),
                "doc_type": self.metadata_mapper.get_value_for_metadata("doc_type"),
                "doc_event_id": self.metadata_mapper.get_value_for_metadata(
                    "doc_event_id"
                ),
                "doc_group_id": self.metadata_mapper.get_value_for_metadata(
                    "doc_group_id"
                ),
                "hitl_operation_id": _hitl_op_id,
                "created_at": self.metadata_mapper.get_value_for_metadata("created_at"),
                "updated_at": self.metadata_mapper.get_value_for_metadata("updated_at"),
                "destination_table_id": self.destination_table_id,
            }
            logging.debug("Will insert into doc_reference table:")
            logging.debug(bq_row)
            storage_manager.write_record("doc_reference", bq_row)
        else:
            # Existing document that was sent for HITL review
            # Retrieve info stored when the doc was first processed

            query = f"""
                SELECT
                doc_id, file_name, doc_status, doc_type, doc_event_id, doc_group_id, created_at, destination_table_id
                FROM `{self.destination_project_id}.{self.destination_dataset_id}.doc_reference`
                WHERE hitl_operation_id = @operation_id """
            query_params = [
                {"name": "operation_id", "type": "STRING", "value": self.operation_id}
            ]
            doc_reference_records = storage_manager.get_records(query, query_params)

            if len(doc_reference_records) == 0:
                raise InitialDocRecordNotFoundError(
                    f"Initial hitl reference record not found for hitl_operation_id: {self.operation_id}"
                )
            elif len(doc_reference_records) > 1:
                raise DocAlreadyProcessedError(
                    f"Duplicate hitl reference records found for hitl_operation_id: {self.operation_id}"
                )
            logging.debug("Will now work with the single result")
            doc_ref = doc_reference_records[0]
            _doc_id = doc_ref.get("doc_id")
            _doc_group_id = doc_ref.get("doc_group_id")
            _doc_type = doc_ref.get("doc_type")
            _orig_file_name = doc_ref.get("file_name")
            _doc_created_at = doc_ref.get("created_at")
            self.destination_table_id = doc_ref.get("destination_table_id")
            self._augment_metadata_mapping_info(
                file_name=_orig_file_name,
                hitl_operation_id=self.operation_id,
                doc_group_id=_doc_group_id,
                doc_type=_doc_type,
                doc_status=DocumentState.document_processing_complete,
                created_at=_doc_created_at,
            )
            # Update status in doc_reference table
            try:
                _status_update = {
                    "doc_status": str(DocumentState.document_processing_complete),
                    "updated_at": self.metadata_mapper.get_value_for_metadata(
                        "updated_at"
                    ),
                }
                logging.debug(
                    f"Will update doc_reference record for doc_id = {_doc_id} - "
                    f"New status = {str(DocumentState.document_processing_complete)}"
                )
                storage_manager.update_record(
                    table_id="doc_reference",
                    record_id_name="doc_id",
                    record_id_value=_doc_id,
                    cols_to_update=_status_update,
                )
            except Exception as e:
                # If the original document was processed fairly recently, the row in bq doc_reference table will still
                # be in BQ's streaming buffer and won't be updatable. Ignore this problem
                logging.info(
                    f"Could not update doc_reference table for doc_id = {_doc_id}. Probable cause: row still in BQ "
                    f"streaming buffer: {str(e)}"
                )

        # Process result, validate types, convert as necessary and store in destination BQ table.
        if not storage_manager.does_table_exist(self.destination_table_id):
            raise TableNotFoundError(
                f"Destination table {self.destination_table_id} not found "
                f"in '{self.destination_project_id}.{self.destination_dataset_id}'"
            )

        schema = storage_manager.get_table_schema(self.destination_table_id)
        mapper = BqDocumentMapper(
            document=document,
            bq_schema=schema,
            metadata_mapper=self.metadata_mapper,
            custom_fields=self.custom_fields,
            include_raw_entities=self.include_raw_entities,
            include_error_fields=self.include_error_fields,
            parsing_methodology=self.parsing_methodology,
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
                    bq_row_attempt_2 = mapper.to_bq_row(exclude_fields=exclude_fields)
                    insert_2_errors = storage_manager.write_record(
                        self.destination_table_id, bq_row_attempt_2
                    )
                    self.log_bq_errors(current_try, insert_2_errors)
                    exclude_fields.extend(mapper.process_insert_errors(insert_2_errors))
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

        return document

    @staticmethod
    def log_bq_errors(retry, errors):
        if errors:
            logging.warning(
                "BQ submission insert errors from attempt %s: %s", retry, errors
            )
        else:
            logging.info("BQ submission insert attempt %s succeeded", retry)

    # Augment the configured metadata mapping info with default values that can be derived by the connector itself
    def _augment_metadata_mapping_info(
        self,
        file_name=None,
        hitl_operation_id=None,
        doc_group_id=None,
        doc_type=None,
        doc_status=None,
        created_at=None,
    ):
        doc_unique_id = str(uuid.uuid4())
        if self.metadata_mapper is not None:
            self.metadata_mapper.set_default_value_for_metadata_if_not_set(
                "file_name", file_name
            )
            self.metadata_mapper.set_default_value_for_metadata_if_not_set(
                "doc_status", str(doc_status)
            )
            self.metadata_mapper.set_default_value_for_metadata_if_not_set(
                "doc_type", str(doc_type)
            )
            self.metadata_mapper.set_default_value_for_metadata_if_not_set(
                "doc_event_id", doc_unique_id
            )
            _doc_group_id = doc_group_id if doc_group_id is not None else doc_unique_id
            self.metadata_mapper.set_default_value_for_metadata_if_not_set(
                "doc_group_id", _doc_group_id
            )
            self.metadata_mapper.set_default_value_for_metadata_if_not_set(
                "hitl_operation_id", hitl_operation_id
            )
            _now_timestamp = datetime.now().isoformat()
            _doc_created_at = _now_timestamp if created_at is None else created_at
            self.metadata_mapper.set_default_value_for_metadata_if_not_set(
                "created_at", _doc_created_at
            )
            self.metadata_mapper.set_default_value_for_metadata_if_not_set(
                "updated_at", _now_timestamp
            )
        return doc_unique_id
