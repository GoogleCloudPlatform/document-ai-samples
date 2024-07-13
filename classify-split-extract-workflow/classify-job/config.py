#!/usr/bin/env python3

"""
Copyright 2024 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import datetime
import json
import os
from typing import Optional, Dict

import google.auth
from google.cloud import storage
from logging_handler import Logger

logger = Logger.get_logger(__file__)

# Environment variables and default settings
PROJECT_ID = os.environ.get("PROJECT_ID")
if not PROJECT_ID:
  _, PROJECT_ID = google.auth.default()

CLASSIFY_INPUT_BUCKET = os.environ.get("CLASSIFY_INPUT_BUCKET", f"{PROJECT_ID}-documents")
CLASSIFY_OUTPUT_BUCKET = os.environ.get("CLASSIFY_OUTPUT_BUCKET", f"{PROJECT_ID}-workflow")
INPUT_FILE = os.environ.get("INPUT_FILE")
GOOGLE_APPLICATION_CREDENTIALS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
OUTPUT_FILE_JSON = os.environ.get("OUTPUT_FILE_JSON", "classify_output.json")
OUTPUT_FILE_CSV = os.environ.get("OUTPUT_FILE_CSV", "classify_output.csv")
CALL_BACK_URL = os.environ.get("CALL_BACK_URL")
BQ_DATASET_ID_PROCESSED_DOCS = os.environ.get("BQ_DATASET_ID_PROCESSED_DOCS", "processed_documents")
BQ_OBJECT_TABLE_RETENTION_DAYS = int(os.environ.get("BQ_OBJECT_TABLE_RETENTION_DAYS", 7))
BQ_DATASET_ID_MLOPS = os.environ.get("BQ_DATASET_ID_MLOPS", "mlops")
BQ_PROJECT_ID = os.environ.get("BQ_PROJECT_ID", PROJECT_ID)
BQ_REGION = os.environ.get("BQ_REGION", "us")
BQ_GCS_CONNECTION_NAME = os.environ.get("BQ_GCS_CONNECTION_NAME", "bq-connection-gcs")
START_PIPELINE_FILENAME = "START_PIPELINE"
CLASSIFIER = "classifier"
DOCAI_OUTPUT_BUCKET = os.environ.get("DOCAI_OUTPUT_BUCKET", f"{PROJECT_ID}-docai-output")
CONFIG_BUCKET = os.environ.get("CONFIG_BUCKET", f"{PROJECT_ID}-config")
CONFIG_FILE_NAME = "config_4medica.json"
CLASSIFICATION_UNDETECTABLE = "unclassified"
CLOUD_RUN_EXECUTION = os.environ.get("CLOUD_RUN_EXECUTION")
REGION = os.environ.get("REGION")
SPLITTER_OUTPUT_DIR = os.environ.get("SPLITTER_OUTPUT_DIR", "splitter_output")

PDF_EXTENSION = ".pdf"
PDF_MIME_TYPE = "application/pdf"
MIME_TYPES = [
  PDF_MIME_TYPE,
  # "image/gif",  # TODO: Add/Check support for all these types
  # "image/tiff",
  # "image/jpeg",
  # "image/png",
  # "image/bmp",
  # "image/webp"
]

NO_CLASSIFIER_LABEL = "No Classifier"
METADATA_CONFIDENCE = "confidence"
METADATA_DOCUMENT_TYPE = "type"


FULL_JOB_NAME = f"projects/{PROJECT_ID}/locations/{REGION}/jobs/classify-job"

# Global variables
gcs = None
bucket = None
last_modified_time_of_object = datetime.datetime.now()
config_data = None

logger.info(
  f"Settings used: CLASSIFY_INPUT_BUCKET=gs://{CLASSIFY_INPUT_BUCKET}, INPUT_FILE={INPUT_FILE}, "
  f"CLASSIFY_OUTPUT_BUCKET=gs://{CLASSIFY_OUTPUT_BUCKET}, OUTPUT_FILE_JSON={OUTPUT_FILE_JSON}, "
  f"OUTPUT_FILE_CSV={OUTPUT_FILE_CSV}, CALL_BACK_URL={CALL_BACK_URL}, "
  f"BQ_DATASET_ID_PROCESSED_DOCS={BQ_DATASET_ID_PROCESSED_DOCS}, BQ_DATASET_ID_MLOPS={BQ_DATASET_ID_MLOPS}, "
  f"BQ_PROJECT_ID={BQ_PROJECT_ID}, BQ_GCS_CONNECTION_NAME={BQ_GCS_CONNECTION_NAME}, "
  f"DOCAI_OUTPUT_BUCKET={DOCAI_OUTPUT_BUCKET}"
)


def init_bucket(bucket_name: str, filename: str) -> None:
  """
  Initializes the GCS bucket.

  Args:
      bucket_name (str): The name of the bucket.
      filename (str): The filename to check in the bucket.
  """
  global gcs
  if not gcs:
    gcs = storage.Client()

  global bucket
  if not bucket:
    if bucket_name and gcs.get_bucket(bucket_name).exists():
      bucket = gcs.get_bucket(bucket_name)
    else:
      logger.error(f"Error: file does not exist gs://{bucket_name}/{filename}")


def get_parser_name_by_doc_type(doc_type: str) -> Optional[str]:
  """
  Retrieves the parser name by document type.

  Args:
      doc_type (str): The document type.

  Returns:
      Optional[str]: The parser name.
  """
  doc = get_document_types_config().get(doc_type)
  if not doc:
    logger.error(f"doc_type {doc_type} not present in document_types_config")
    return None
  return doc.get("parser")


def get_parser_config() -> Dict:
  """
  Retrieves the parser configuration.

  Returns:
      Dict: The parser configuration.
  """
  return get_config("parser_config")


def get_document_types_config() -> Dict:
  """
  Retrieves the document types configuration.

  Returns:
      Dict: The document types configuration.
  """
  return get_config("document_types_config")


def get_parser_by_doc_type(doc_type: str) -> Optional[Dict]:
  """
  Retrieves the parser by document type.

  Args:
      doc_type (str): The document type.

  Returns:
      Optional[Dict]: The parser configuration.
  """
  doc = get_document_types_config().get(doc_type)
  if not doc:
    logger.error(f"doc_type {doc_type} not present in document_types_config")
    return None

  parser_name = doc.get("parser")
  return get_parser_config().get(parser_name)


def get_config(config_name: Optional[str] = None) -> Dict:
  """
  Retrieves the configuration data.

  Args:
      config_name (Optional[str]): The configuration name.

  Returns:
      Dict: The configuration data.
  """
  config_data_loaded = load_config(CONFIG_BUCKET, CONFIG_FILE_NAME)
  assert config_data_loaded, f"Unable to locate '{config_name}' or incorrect JSON file"

  if config_name:
    config_item = config_data_loaded.get(config_name, {})
  else:
    config_item = config_data_loaded
  return config_item


def load_config(bucket_name: str, filename: str) -> Optional[Dict]:
  """
  Loads the configuration data from a GCS bucket or local file.

  Args:
      bucket_name (str): The GCS bucket name.
      filename (str): The configuration file name.

  Returns:
      Optional[Dict]: The configuration data.
  """
  global bucket
  if not bucket:
    init_bucket(bucket_name, filename)

  blob = bucket.get_blob(filename)
  last_modified_time = blob.updated
  global last_modified_time_of_object
  global config_data
  if last_modified_time == last_modified_time_of_object:
    return config_data
  else:
    logger.info(f"load_config - Reloading config from: {filename}")
    try:
      if blob.exists():
        config_data = json.loads(blob.download_as_text(encoding="utf-8"))
        last_modified_time_of_object = last_modified_time
        return config_data
      else:
        logger.error(f"load_config - Error: file does not exist gs://{bucket_name}/{filename}")
    except Exception as e:
      logger.error(f"load_config - Error: while obtaining file from GCS gs://{bucket_name}/{filename} {e}")
      # Fall-back to local file
      logger.warning(f"load_config - Warning: Using local {filename}")
      with open(os.path.join(os.path.dirname(__file__), "config", filename)) as json_file:
        config_data = json.load(json_file)
        return config_data


def get_docai_settings() -> Dict:
  """
  Retrieves the Document AI settings configuration.

  Returns:
      Dict: The Document AI settings configuration.
  """
  return get_config("settings_config")


def get_classification_confidence_threshold() -> float:
  """
  Retrieves the classification confidence threshold.

  Returns:
      float: The classification confidence threshold.
  """
  settings = get_docai_settings()
  return float(settings.get("classification_confidence_threshold", 0))


def get_classification_default_class() -> str:
  """
  Retrieves the default classification class.

  Returns:
      str: The default classification class.
  """
  settings = get_docai_settings()
  classification_default_class = settings.get("classification_default_class", CLASSIFICATION_UNDETECTABLE)
  parser = get_parser_by_doc_type(classification_default_class)
  if parser:
    return classification_default_class

  logger.warning(
    f"Classification default label {classification_default_class} is not a valid Label or missing a corresponding "
    f"parser in parser_config"
  )
  return CLASSIFICATION_UNDETECTABLE


def get_document_class_by_classifier_label(label_name: str) -> Optional[str]:
  """
  Retrieves the document class by classifier label.

  Args:
      label_name (str): The classifier label name.

  Returns:
      Optional[str]: The document class.
  """
  for k, v in get_document_types_config().items():
    if v.get("classifier_label") == label_name:
      return k
  logger.error(f"classifier_label={label_name} is not assigned to any document in the config")
  return None


def get_parser_by_name(parser_name: str) -> Optional[Dict]:
  """
  Retrieves the parser configuration by parser name.

  Args:
      parser_name (str): The parser name.

  Returns:
      Optional[Dict]: The parser configuration.
  """
  return get_parser_config().get(parser_name)


def get_model_name(document_type: str) -> Optional[str]:
  """
  Retrieves the model name by document type.

  Args:
      document_type (str): The document type.

  Returns:
      Optional[str]: The model name.
  """
  parser = get_parser_by_doc_type(document_type)
  if parser:
    parser_name = get_parser_name_by_doc_type(document_type)
    model_name = f"{BQ_PROJECT_ID}.{BQ_DATASET_ID_MLOPS}.{parser.get('model_name', parser_name.upper() + '_MODEL')}"
  else:
    logger.warning(f"No parser found for document type {document_type}")
    return None

  logger.info(f"model_name={model_name}")
  return model_name


def get_out_table_name(document_type: str) -> Optional[str]:
  """
  Retrieves the output table name by document type.

  Args:
      document_type (str): The document type.

  Returns:
      Optional[str]: The output table name.
  """
  parser = get_parser_by_doc_type(document_type)
  if parser:
    parser_name = get_parser_name_by_doc_type(document_type)
    out_table_name = f"{BQ_PROJECT_ID}.{BQ_DATASET_ID_PROCESSED_DOCS}.{parser.get('out_table_name', parser_name.upper() + '_DOCUMENTS')}"
  else:
    logger.warning(f"No parser found for document type {document_type}")
    return None

  logger.info(f"out_table_name={out_table_name}")
  return out_table_name
