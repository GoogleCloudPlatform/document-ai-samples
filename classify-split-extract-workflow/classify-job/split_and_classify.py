# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pylint: disable=logging-fstring-interpolation,import-error,too-many-locals

"""
Module for splitting and classifying documents using Google Cloud Document AI.
This module includes functions for batch classification of documents, processing
classification results, splitting PDF files based on classification, and handling
metadata and callbacks.
"""

import json
import os
import re
from typing import Dict, Optional, List, Tuple

from google.cloud.documentai_toolbox import gcs_utilities
from google.cloud import documentai_v1 as documentai
from google.cloud import storage
from google.cloud.documentai_v1.types.document import Document
from google.cloud.documentai_v1.types.document_processor_service import BatchProcessMetadata
from pikepdf import Pdf

import config
import docai_helper
import gcs_helper
import utils
import bq_mlops
from config import (
    DOCAI_OUTPUT_BUCKET, NO_CLASSIFIER_LABEL, METADATA_CONFIDENCE,
    METADATA_DOCUMENT_TYPE, SPLITTER_OUTPUT_DIR)
from logging_handler import Logger

storage_client = storage.Client()
logger = Logger.get_logger(__file__)


def batch_classification(
        processor: documentai.types.processor.Processor,
        dai_client: documentai.DocumentProcessorServiceClient,
        input_uris: List[str]
) -> Optional[Dict]:
    """Performs batch classification on a list of documents using Document AI."""
    logger.info(f"input_uris = {input_uris}")
    if not input_uris:
        return None

    input_docs = [
        documentai.GcsDocument(gcs_uri=doc_uri, mime_type=config.PDF_MIME_TYPE)
        for doc_uri in input_uris
    ]
    gcs_documents = documentai.GcsDocuments(documents=input_docs)
    input_config = documentai.BatchDocumentsInputConfig(gcs_documents=gcs_documents)

    gcs_output_uri = f"gs://{DOCAI_OUTPUT_BUCKET}"
    timestamp = utils.get_utc_timestamp()
    gcs_output_uri_prefix = "classifier_out_" + timestamp
    destination_uri = f"{gcs_output_uri}/{gcs_output_uri_prefix}/"
    output_config = documentai.DocumentOutputConfig(
        gcs_output_config={"gcs_uri": destination_uri}
    )

    logger.info(f"input_config = {input_config}, output_config = {output_config}")
    logger.info(
        f"Calling DocAI API for {len(input_uris)} document(s) "
        f"using {processor.display_name} processor "
        f"type={processor.type_}, path={processor.name}"
    )

    request = documentai.types.document_processor_service.BatchProcessRequest(
        name=processor.name,
        input_documents=input_config,
        document_output_config=output_config,
    )
    operation = dai_client.batch_process_documents(request)

    logger.info(f"Waiting for operation {operation.operation.name} to complete...")
    operation.result()

    metadata: BatchProcessMetadata = documentai.BatchProcessMetadata(operation.metadata)
    return process_classify_results(metadata)


def process_classify_results(metadata: BatchProcessMetadata) -> Optional[Dict]:
    """Processes the results of a classification operation."""
    logger.info(f"handling classification results - operation.metadata={metadata}")

    documents = {}

    if metadata.state != documentai.BatchProcessMetadata.State.SUCCEEDED:
        raise ValueError(f"Batch Process Failed: {metadata.state_message}")

    for process in metadata.individual_process_statuses:
        matches = re.match(r"gs://(.*?)/(.*)", process.output_gcs_destination)
        if matches:
            output_bucket, output_prefix = matches.groups()
        else:
            logger.error(f"Invalid GCS destination format: {process.output_gcs_destination}")
            continue
        input_gcs_source = process.input_gcs_source

        logger.info(
            f"output_bucket = {output_bucket}, "
            f"output_prefix={output_prefix}, "
            f"input_gcs_source = {input_gcs_source}, "
            f"output_gcs_destination = {process.output_gcs_destination}"
        )

        # Adding support for shards using toolbox after the issue is addressed
        # https://github.com/googleapis/python-documentai-toolbox/issues/332
        output_blob = list(storage_client.list_blobs(output_bucket, prefix=output_prefix + "/"))[0]

        if ".json" not in output_blob.name:
            logger.info(
                f"Skipping non-supported file: {output_blob.name} - Mimetype: "
                f"{output_blob.content_type}"
            )
            continue

        document_out = documentai.Document.from_json(
            output_blob.download_as_bytes(), ignore_unknown_fields=True
        )
        blob_entities = document_out.entities

        if not blob_entities:
            logger.info(f"No entities found for {input_gcs_source}")
            continue

        if is_splitting_required(blob_entities):
            documents = split_pdf(input_gcs_source, blob_entities)
        else:
            max_confidence_entity = max(blob_entities, key=lambda item: item.confidence)
            metadata = get_metadata(max_confidence_entity)
            gcs_helper.add_metadata(input_gcs_source, metadata)

            add_predicted_document_type(metadata, input_gcs_source=input_gcs_source,
                                        documents=documents)

    return documents


def get_metadata(entity: Optional[Document.Entity] = None) -> Dict:
    """Get metadata from a Document AI entity."""
    if not entity:
        confidence = -1
        document_type = NO_CLASSIFIER_LABEL
    else:
        confidence = round(entity.confidence, 3)
        document_type = entity.type_

    return {
        METADATA_CONFIDENCE: confidence,
        METADATA_DOCUMENT_TYPE: document_type,
    }


def add_predicted_document_type(metadata: dict, input_gcs_source: str, documents: Dict) -> None:
    """Add predicted document type to the documents dictionary."""
    classification_default_class = config.get_classification_default_class()

    predicted_confidence = metadata[METADATA_CONFIDENCE]
    predicted_label = metadata[METADATA_DOCUMENT_TYPE]
    if check_confidence_threshold_passed(predicted_confidence):
        predicted_class = config.get_document_class_by_classifier_label(predicted_label)
    else:
        logger.warning(
            f"Using default document type={classification_default_class} for {input_gcs_source},"
            f" due to low confidence={predicted_confidence}")
        predicted_class = classification_default_class

    if not predicted_class:
        logger.warning(
            f"No document type found for {predicted_label} and no default one defined, "
            f"using the default class = {classification_default_class}")
        predicted_class = classification_default_class

    if predicted_class not in documents:
        documents[predicted_class] = []
        documents[predicted_class].append(input_gcs_source)


def handle_no_classifier(f_uris: List[str]) -> Dict:
    """Handles cases where no classifier is used."""
    documents: Dict[str, List[str]] = {}
    for uri in f_uris:
        add_predicted_document_type(get_metadata(), input_gcs_source=uri, documents=documents)

    return documents


def stream_classification_results(call_back_url: str, bucket_name: Optional[str],
                                  file_name: Optional[str]):
    """Streams classification results to a specified callback URL."""
    logger.info(f"bucket={bucket_name}, blob_object={file_name}")
    success = bool(bucket_name and file_name)
    result = "Classification Job completed successfully, proceed with extraction" if success else \
        "Classification Job failed"

    payload = {
        "result": result,
        "success": success,
        "bucket": bucket_name,
        "object": file_name,
    }

    utils.send_callback_request(call_back_url, payload)


def save_classification_results(classified_items: Dict) -> Tuple[Optional[str], Optional[str]]:
    """Saves classification results to Google Cloud Storage."""
    payload_data = []
    try:
        for document_type, f_uris in classified_items.items():
            model_name, out_table_name = config.get_model_name_table_name(document_type)
            processor_name = config.get_parser_name_by_doc_type(document_type)
            if processor_name:
                processor, _ = docai_helper.get_processor_and_client(processor_name)
            else:
                logger.error(f"No processor found for document type: {document_type}")
                continue

            object_table_name = bq_mlops.object_table_create(f_uris=f_uris,
                                                             document_type=document_type)
            bq_mlops.remote_model_create(processor=processor, model_name=model_name)

            payload_data.append({
                "object_table_name": object_table_name,
                "model_name": model_name,
                "out_table_name": out_table_name
            })

        if not payload_data:
            logger.warning("Payload data is empty, skipping")
            return None, None

        prefix = utils.get_utc_timestamp()

        bucket, blob_object = gcs_helper.write_data_to_gcs(
            bucket_name=config.CLASSIFY_OUTPUT_BUCKET,
            blob_name=f"{prefix}_{config.OUTPUT_FILE_JSON}",
            content=json.dumps(payload_data, indent=4),
            mime_type='application/json'
        )
    except (json.JSONDecodeError, OSError, ValueError) as e:
        logger.error(f"Exception while saving classification results: {e}")
        return None, None

    logger.info(f"Saved classification results to, bucket={bucket}, file_name={blob_object}")
    return bucket, blob_object


def is_splitting_required(entities: List[Document.Entity]) -> bool:
    """Check if splitting is required based on entities."""
    try:
        return not all(len(entity.page_anchor.page_refs) == 0 or
                       all(not ref for ref in entity.page_anchor.page_refs) for entity in entities)
    except AttributeError:
        return False


def check_confidence_threshold_passed(predicted_confidence: float) -> bool:
    """Check if the confidence threshold is passed."""
    confidence_threshold = config.get_classification_confidence_threshold()
    if predicted_confidence < confidence_threshold:
        logger.warning(f"Confidence threshold not passed for "
                       f"{predicted_confidence} < {confidence_threshold}")
        return False
    return True


def split_pdf(gcs_uri: str, entities: List[Document.Entity]) -> Dict:
    """Splits local PDF file into multiple PDF files based on output from a
    Splitter/Classifier processor.

    Args:
      gcs_uri (str):
          Required. The path to the PDF file.
      entities (List[Document.Entity]):
          Required. The list of entities to be split.
    Returns:
      List[str]:
          A list of output pdf files.
    """

    documents: Dict = {}

    if len(entities) == 1:
        metadata = get_metadata(entities[0])
        metadata.update({
            "original": gcs_uri
        })

        gcs_helper.add_metadata(gcs_uri=gcs_uri, metadata=metadata)
        add_predicted_document_type(metadata=metadata, input_gcs_source=gcs_uri,
                                    documents=documents)
    else:
        temp_local_dir = os.path.join(os.path.dirname(__file__), "temp_files",
                                      utils.get_utc_timestamp())
        if not os.path.exists(temp_local_dir):
            os.makedirs(temp_local_dir)

        pdf_path = os.path.join(temp_local_dir, os.path.basename(gcs_uri))
        gcs_helper.download_file(gcs_uri=gcs_uri, output_filename=pdf_path)

        input_filename, input_extension = os.path.splitext(os.path.basename(pdf_path))
        bucket_name, _ = gcs_utilities.split_gcs_uri(gcs_uri)

        with Pdf.open(pdf_path) as pdf:
            for entity in entities:
                subdoc_type = entity.type_ or "subdoc"
                page_refs = entity.page_anchor.page_refs
                if page_refs:
                    start_page = int(page_refs[0].page)
                    end_page = int(page_refs[-1].page)
                else:
                    logger.warning(f"Skipping {pdf_path} entity due to no page refs, no splitting")
                    continue
                page_range = (
                    f"pg{start_page + 1}"
                    if start_page == end_page
                    else f"pg{start_page + 1}-{end_page + 1}"
                )
                output_filename = (
                    f"{input_filename}_{page_range}_{subdoc_type}{input_extension}"
                )
                metadata = get_metadata(entity)
                metadata.update({
                    "original": gcs_uri
                })

                gcs_path = gcs_utilities.split_gcs_uri(os.path.dirname(gcs_uri))[1]
                destination_blob_name = os.path.join(gcs_path, SPLITTER_OUTPUT_DIR, output_filename)
                destination_blob_uri = f"gs://{bucket_name}/{destination_blob_name}"

                local_out_file = os.path.join(temp_local_dir, output_filename)

                subdoc = Pdf.new()
                subdoc.pages.extend(pdf.pages[start_page: end_page + 1])
                subdoc.save(local_out_file, min_version=pdf.pdf_version)

                gcs_helper.upload_file(bucket_name=bucket_name, source_file_name=local_out_file,
                                       destination_blob_name=destination_blob_name)
                gcs_helper.add_metadata(destination_blob_uri, metadata)

                add_predicted_document_type(metadata=metadata,
                                            input_gcs_source=destination_blob_uri,
                                            documents=documents)

        utils.delete_directory(temp_local_dir)
    return documents
