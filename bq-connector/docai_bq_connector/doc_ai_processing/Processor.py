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
import re
import uuid
from typing import Union

from google.cloud import documentai_v1 as documentai
from google.cloud import storage

from docai_bq_connector.doc_ai_processing.DocumentOperation import DocumentOperation
from docai_bq_connector.doc_ai_processing.ProcessedDocument import ProcessedDocument
from docai_bq_connector.exception.InvalidGcsUriError import InvalidGcsUriError
from docai_bq_connector.helper.gcs_util import get_gcs_blob, write_gcs_blob
from docai_bq_connector.helper.pdf_util import get_pdf_page_cnt

CONTENT_TYPE_PDF = "application/pdf"
CONTENT_TYPE_JSON = "application/json"


class Processor:
    def __init__(
        self,
        bucket_name: str,
        file_name: str,
        content_type: str,
        processor_project_id: str,
        processor_location: str,
        processor_id: str,
        extraction_result_output_bucket: str,
        async_output_folder_gcs_uri: str,
        sync_timeout: int = 900,
        async_timeout: int = 900,
        should_async_wait: bool = True,
        should_write_extraction_result: bool = True,
        max_sync_page_count: int = 5,
    ):
        self.bucket_name = bucket_name
        self.file_name = file_name
        self.content_type = content_type
        self.processor_project_id = processor_project_id
        self.processor_location = processor_location
        self.processor_id = processor_id
        self.extraction_result_output_bucket = extraction_result_output_bucket
        self.async_output_folder_gcs_uri = async_output_folder_gcs_uri
        self.sync_timeout = sync_timeout
        self.async_timeout = async_timeout
        self.should_async_wait = should_async_wait
        self.max_sync_page_count = max_sync_page_count
        if should_write_extraction_result and extraction_result_output_bucket is None:
            raise Exception(
                "extraction_result_output_bucket should be set when should_write_extraction_result is set to True"
            )
        self.should_write_extraction_result = should_write_extraction_result

    def _get_gcs_blob(self):
        return get_gcs_blob(self.bucket_name, self.file_name)

    def _get_input_uri(self):
        return f"gs://{self.bucket_name}/{self.file_name}"

    def _get_document_ai_options(self):
        return {"api_endpoint": f"{self.processor_location}-documentai.googleapis.com"}

    def _write_result_to_gcs(self, json_result_as_str):
        if self.should_write_extraction_result:
            split_fname = self.file_name.split(".")[0]
            json_file_name = f"{split_fname}.json"
            write_gcs_blob(
                self.extraction_result_output_bucket,
                json_file_name,
                json_result_as_str,
                content_type="application/json",
            )

    # TODO: Support for processing multiple files
    def _process_sync(
        self, document_blob: bytes
    ) -> Union[DocumentOperation, ProcessedDocument]:
        """
        This uses Doc AI to process the document synchronously.
        Args:
            gcs_blob:
            content_type:
            project_number:
            location:
            processor_id:

        Returns:
            Document AI document object
            HITL operation ID
            Document Object as a json object
        """
        # You must set the api_endpoint if you use a location other than 'us', e.g.:
        opts = self._get_document_ai_options()
        client = documentai.DocumentProcessorServiceClient(client_options=opts)

        document = {"content": document_blob, "mime_type": self.content_type}

        processor_uri = client.processor_path(
            self.processor_project_id, self.processor_location, self.processor_id
        )
        request = {"name": processor_uri, "raw_document": document}
        logging.info(
            f"Invoking name: {processor_uri}, mime_type: {self.content_type} in sync mode"
        )

        results = client.process_document(request)
        logging.debug(f"HITL Output: {results.human_review_status}")

        hitl_op = results.human_review_status.human_review_operation
        hitl_op_id = None
        if hitl_op:
            hitl_op_split = hitl_op.split("/")
            hitl_op_id = hitl_op_split.pop()

        # This method will sometimes run out of memory if the document is big enough
        # It seems to work fine if # of pages <= 5
        results_json = documentai.types.Document.to_json(results.document)
        return ProcessedDocument(
            document=results.document,
            dictionary=results_json,
            hitl_operation_id=hitl_op_id,
        )

    def _process_async(self) -> Union[DocumentOperation, ProcessedDocument]:
        # if self.should_async_wait is True:
        # return type of ProcessedDocument
        # else return type of DocumentOperation
        """
        This uses Doc AI to process the document asynchronously.  The limit is 100 pages.
        Args:
            gcs_blob:
            content_type:
            project_number:
            location:
            processor_id:
            gcs_output_uri:
            gcs_output_uri_prefix:
            timeout:
        Returns:

        """
        # You must set the api_endpoint if you use a location other than 'us', e.g.:
        opts = self._get_document_ai_options()
        client = documentai.DocumentProcessorServiceClient(client_options=opts)

        # Add a unique folder to the uri for this particular async operation
        unique_folder = uuid.uuid4().hex

        if self.async_output_folder_gcs_uri is None:
            raise Exception(
                "--async_output_folder_gcs_uri must be set when a document is processed asynchronously"
            )
        destination_uri = f"{self.async_output_folder_gcs_uri}/{unique_folder}"

        gcs_documents = documentai.GcsDocuments(
            documents=[
                {"gcs_uri": self._get_input_uri(), "mime_type": self.content_type}
            ]
        )

        # 'mime_type' can be 'application/pdf', 'image/tiff',
        # and 'image/gif', or 'application/json'
        input_config = documentai.BatchDocumentsInputConfig(gcs_documents=gcs_documents)

        # Where to write results
        output_config = documentai.DocumentOutputConfig(
            gcs_output_config={"gcs_uri": destination_uri}
        )

        processor_uri = client.processor_path(
            self.processor_project_id, self.processor_location, self.processor_id
        )
        request = documentai.types.document_processor_service.BatchProcessRequest(
            name=processor_uri,
            input_documents=input_config,
            document_output_config=output_config,
            skip_human_review=False,  # TODO: Add supporting input arg.
        )

        operation = client.batch_process_documents(request)
        logging.debug(f"DocAI Batch Process started. LRO = {operation.operation.name}")

        if self.should_async_wait is False:
            return DocumentOperation(operation.operation.name)

        # Wait for the operation to finish
        operation.result(timeout=self.async_timeout)
        logging.debug("DocAI Batch Process finished")

        if operation.metadata and operation.metadata.individual_process_statuses:
            cur_process_status = operation.metadata.individual_process_statuses[0]
            hitl_gcs_output = cur_process_status.output_gcs_destination
            hitl_op_full_path = (
                cur_process_status.human_review_status.human_review_operation
            )
        else:
            # Fallback to using the GCS path set in the request
            hitl_gcs_output = output_config
            hitl_op_full_path = None

        # Results are written to GCS. Use a regex to find
        # output files
        match = re.match(r"gs://([^/]+)/(.+)", hitl_gcs_output)
        if match:
            output_bucket = match.group(1)
            prefix = match.group(2)
        else:
            raise InvalidGcsUriError(
                "The supplied async_output_folder_gcs_uri is not a properly structured GCS Path"
            )

        storage_client = storage.Client()
        bucket = storage_client.get_bucket(output_bucket)
        blob_list = list(bucket.list_blobs(prefix=prefix))
        # should always be a single document here
        for i, blob in enumerate(blob_list):
            # If JSON file, download the contents of this blob as a bytes object.
            if blob.content_type == "application/json":
                blob_as_bytes = blob.download_as_bytes()

                document = documentai.Document.from_json(
                    blob_as_bytes, ignore_unknown_fields=True
                )
                logging.debug(f"Fetched file {i + 1}: {blob.name}")
            else:
                logging.info(f"Skipping non-supported file type {blob.name}")

        # Delete the unique folder created for this operation
        blobs = list(bucket.list_blobs(prefix=prefix))
        bucket.delete_blobs(blobs)
        hitl_op_id = None
        if hitl_op_full_path:
            logging.debug(f"Async processing returned hitl_op = {hitl_op_full_path}")
            hitl_op_id = hitl_op_full_path.split("/").pop()

        return ProcessedDocument(
            document=document, dictionary=blob_as_bytes, hitl_operation_id=hitl_op_id
        )

    def _process_hitl_output(self, gcs_blob: bytes) -> ProcessedDocument:
        document = documentai.types.Document.from_json(
            gcs_blob, ignore_unknown_fields=True
        )
        return ProcessedDocument(
            document=document, dictionary=gcs_blob, hitl_operation_id=None
        )

    def process(self) -> Union[DocumentOperation, ProcessedDocument]:
        gcs_doc_blob, gcs_doc_meta = self._get_gcs_blob()
        if self.content_type == CONTENT_TYPE_PDF:
            # Original document. Needs to be processed by a DocAI extractor
            page_count = get_pdf_page_cnt(gcs_doc_blob)
            # Limit is different per processor: https://cloud.google.com/document-ai/quotas
            if page_count <= self.max_sync_page_count:
                process_result = self._process_sync(document_blob=gcs_doc_blob)
            else:
                process_result = self._process_async()
            if (
                isinstance(process_result, ProcessedDocument)
                and process_result is not None
            ):
                self._write_result_to_gcs(process_result.dictionary)
        elif self.content_type == CONTENT_TYPE_JSON:
            # This document was already processed and sent for HITL review. The result must now be processed
            logging.debug(
                f"Read DocAI HITL Output file = {self.bucket_name}/{self.file_name}"
            )
            process_result = self._process_hitl_output(gcs_doc_blob)
        else:
            logging.info(
                f"Skipping non-supported file type {self.file_name} with content type = {self.content_type}"
            )

        return process_result
