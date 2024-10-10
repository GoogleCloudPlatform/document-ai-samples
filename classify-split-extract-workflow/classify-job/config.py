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

"""
This module handles the configuration for the workflow.
It includes functionality for loading configurations from Google Cloud Storage (GCS),
retrieving specific configuration elements.
"""
import datetime
import json
import os
from typing import Any, cast, Dict, Optional, Tuple

import google.auth
from google.cloud import run_v2
from google.cloud import storage
from logging_handler import Logger

# pylint: disable=logging-fstring-interpolation,import-error,global-statement


logger = Logger.get_logger(__file__)

# Environment variables and default settings
PROJECT_ID = os.environ.get("PROJECT_ID") or google.auth.default()[1]

CLASSIFY_INPUT_BUCKET = os.environ.get(
    "CLASSIFY_INPUT_BUCKET", f"{PROJECT_ID}-documents"
)
CLASSIFY_OUTPUT_BUCKET = os.environ.get(
    "CLASSIFY_OUTPUT_BUCKET", f"{PROJECT_ID}-workflow"
)
INPUT_FILE = os.environ.get("INPUT_FILE")
GOOGLE_APPLICATION_CREDENTIALS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
OUTPUT_FILE_JSON = os.environ.get("OUTPUT_FILE_JSON", "classify_output.json")
OUTPUT_FILE_CSV = os.environ.get("OUTPUT_FILE_CSV", "classify_output.csv")
CALL_BACK_URL = os.environ.get("CALL_BACK_URL")
BQ_DATASET_ID_PROCESSED_DOCS = os.environ.get(
    "BQ_DATASET_ID_PROCESSED_DOCS", "processed_documents"
)
BQ_OBJECT_TABLE_RETENTION_DAYS = int(
    os.environ.get("BQ_OBJECT_TABLE_RETENTION_DAYS", 7)
)
BQ_DATASET_ID_MLOPS = os.environ.get("BQ_DATASET_ID_MLOPS", "mlops")
BQ_PROJECT_ID = os.environ.get("BQ_PROJECT_ID", PROJECT_ID)
BQ_REGION = os.environ.get("BQ_REGION", "us")
BQ_GCS_CONNECTION_NAME = os.environ.get("BQ_GCS_CONNECTION_NAME", "bq-connection-gcs")
START_PIPELINE_FILENAME = "START_PIPELINE"
CLASSIFIER = "classifier"
DOCAI_OUTPUT_BUCKET = os.environ.get(
    "DOCAI_OUTPUT_BUCKET", f"{PROJECT_ID}-docai-output"
)
CONFIG_BUCKET = os.environ.get("CONFIG_BUCKET", f"{PROJECT_ID}-config")
CONFIG_FILE_NAME = "config.json"
CLASSIFICATION_UNDETECTABLE = "unclassified"
CLOUD_RUN_EXECUTION = os.environ.get("CLOUD_RUN_EXECUTION")
REGION = os.environ.get("REGION")
SPLITTER_OUTPUT_DIR = os.environ.get("SPLITTER_OUTPUT_DIR", "splitter_output")

PDF_EXTENSION = ".pdf"
PDF_MIME_TYPE = "application/pdf"
MIME_TYPES = [
    PDF_MIME_TYPE,
]

OTHER_MIME_TYPES_TO_SUPPORT = [
    "image/gif",
    "image/tiff",
    "image/jpeg",
    "image/png",
    "image/bmp",
    "image/webp",
]

NO_CLASSIFIER_LABEL = "No Classifier"
METADATA_CONFIDENCE = "confidence"
METADATA_DOCUMENT_TYPE = "type"

CONFIG_JSON_DOCUMENT_TYPES_CONFIG = "document_types_config"
FULL_JOB_NAME = run_v2.ExecutionsClient.job_path(PROJECT_ID, REGION, "classify-job")

# Global variables
BUCKET: Optional[storage.Bucket] = None
LAST_MODIFIED_TIME_OF_CONFIG = datetime.datetime.now()
CONFIG_DATA: Optional[Dict[Any, Any]] = None

logger.info(
    f"Settings used: CLASSIFY_INPUT_BUCKET=gs://{CLASSIFY_INPUT_BUCKET}, INPUT_FILE={INPUT_FILE}, "
    f"CLASSIFY_OUTPUT_BUCKET=gs://{CLASSIFY_OUTPUT_BUCKET}, OUTPUT_FILE_JSON={OUTPUT_FILE_JSON}, "
    f"OUTPUT_FILE_CSV={OUTPUT_FILE_CSV}, CALL_BACK_URL={CALL_BACK_URL}, "
    f"BQ_DATASET_ID_PROCESSED_DOCS={BQ_DATASET_ID_PROCESSED_DOCS}, "
    f"BQ_DATASET_ID_MLOPS={BQ_DATASET_ID_MLOPS}, "
    f"BQ_PROJECT_ID={BQ_PROJECT_ID}, BQ_GCS_CONNECTION_NAME={BQ_GCS_CONNECTION_NAME}, "
    f"DOCAI_OUTPUT_BUCKET={DOCAI_OUTPUT_BUCKET}"
)


def init_bucket(bucket_name: str) -> Optional[storage.Bucket]:
    """
    Initializes the GCS bucket.

    Args:
        bucket_name (str): The name of the bucket.
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    if not bucket.exists():
        logger.error(f"Bucket does not exist: gs://{bucket_name}")
        return None  # Return None to indicate failure
    return bucket


def get_config(
    config_name: Optional[str] = None, element_path: Optional[str] = None
) -> Optional[Dict[Any, Any]]:
    """
    Retrieves the configuration data.

    Args:
        config_name (Optional[str]): The configuration name.
        element_path  (Optional[str]): The element path.

    Returns:
        Optional[Dict[Any, Any]]: The configuration data.
    """
    global CONFIG_DATA
    if not CONFIG_DATA:
        CONFIG_DATA = load_config(CONFIG_BUCKET, CONFIG_FILE_NAME)
        assert CONFIG_DATA, "Unable to load configuration data"

    config_data_loaded = (
        CONFIG_DATA.get(config_name, {}) if config_name else CONFIG_DATA
    )

    if element_path:
        keys = element_path.split(".")
        for key in keys:
            if isinstance(config_data_loaded, dict):
                config_data_loaded_new = config_data_loaded.get(key)
                if config_data_loaded_new is None:
                    logger.error(
                        f"Key '{key}' not present in the "
                        f"configuration {json.dumps(config_data_loaded, indent=4)}"
                    )
                    return None
                config_data_loaded = config_data_loaded_new
            else:
                logger.error(
                    f"Expected a dictionary at '{key}' but found a "
                    f"{type(config_data_loaded).__name__}"
                )
                return None

    return config_data_loaded


def get_parser_name_by_doc_type(doc_type: str) -> Optional[str]:
    """Retrieves the parser name based on the document type.

    Args:
        doc_type (str): The document type.

    Returns:
        Optional[str]: The parser name, or None if not found.
    """
    return cast(
        Optional[str],
        get_config(CONFIG_JSON_DOCUMENT_TYPES_CONFIG, f"{doc_type}.parser"),
    )


def get_document_types_config() -> Optional[Dict[Any, Any]]:
    """
    Retrieves the document types configuration.

    Returns:
        Optional[Dict[Any, Any]]: The document types configuration.
    """
    return get_config(CONFIG_JSON_DOCUMENT_TYPES_CONFIG)


def get_parser_by_doc_type(doc_type: str) -> Optional[Dict[Any, Any]]:
    """
    Retrieves the parser by document type.

    Args:
        doc_type (str): The document type.

    Returns:
        Optional[Dict[Any, Any]]: The parser configuration.
    """
    parser_name = get_parser_name_by_doc_type(doc_type)
    if parser_name:
        return get_config("parser_config", parser_name)
    return None


def load_config(bucket_name: str, filename: str) -> Optional[Dict[Any, Any]]:
    """
    Loads the configuration data from a GCS bucket or local file.

    Args:
        bucket_name (str): The GCS bucket name.
        filename (str): The configuration file name.

    Returns:
        Optional[Dict[Any, Any]]: The configuration data.
    """
    global BUCKET, CONFIG_DATA, LAST_MODIFIED_TIME_OF_CONFIG
    if not BUCKET:
        BUCKET = init_bucket(bucket_name)

    if not BUCKET:
        return None

    blob = BUCKET.get_blob(filename)
    if not blob:
        logger.error(f"Error: file does not exist gs://{bucket_name}/{filename}")
        return None

    last_modified_time = blob.updated
    if LAST_MODIFIED_TIME_OF_CONFIG == last_modified_time:
        return CONFIG_DATA

    logger.info(f"Reloading config from: {filename}")
    try:
        CONFIG_DATA = json.loads(blob.download_as_text(encoding="utf-8"))
        LAST_MODIFIED_TIME_OF_CONFIG = last_modified_time
    except (json.JSONDecodeError, OSError) as e:
        logger.error(
            f"Error while obtaining file from GCS gs://{bucket_name}/{filename}: {e}"
        )
        logger.warning(f"Using local {filename}")
        try:
            with open(
                os.path.join(os.path.dirname(__file__), "config", filename),
                encoding="utf-8",
            ) as json_file:
                CONFIG_DATA = json.load(json_file)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            logger.error(f"Error loading local config file {filename}: {exc}")
            return None

    return CONFIG_DATA


def get_docai_settings() -> Optional[Dict[Any, Any]]:
    """
    Retrieves the Document AI settings configuration.

    Returns:
        Optional[Dict[Any, Any]]: The Document AI settings configuration.
    """
    return get_config("settings_config")


def get_classification_confidence_threshold() -> float:
    """
    Retrieves the classification confidence threshold.

    Returns:
        float: The classification confidence threshold.
    """

    settings = get_docai_settings()
    return (
        float(settings.get("classification_confidence_threshold", 0)) if settings else 0
    )


def get_classification_default_class() -> str:
    """
    Retrieves the default classification class.

    Returns:
        str: The default classification class.
    """

    settings = get_docai_settings()
    classification_default_class = (
        settings.get("classification_default_class", CLASSIFICATION_UNDETECTABLE)
        if settings
        else CLASSIFICATION_UNDETECTABLE
    )
    parser = get_parser_by_doc_type(classification_default_class)
    if parser:
        return classification_default_class

    logger.warning(
        f"Classification default label {classification_default_class}"
        f" is not a valid Label or missing a corresponding "
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
    doc_types_config = get_document_types_config()
    if doc_types_config:
        for k, v in doc_types_config.items():
            if v.get("classifier_label") == label_name:
                return k
    logger.error(
        f"classifier_label={label_name} is not assigned to any document in the config"
    )
    return None


def get_parser_by_name(parser_name: str) -> Optional[Dict[Any, Any]]:
    """
    Retrieves the parser configuration by parser name.

    Args:
        parser_name (str): The parser name.

    Returns:
        Optional[Dict[Any, Any]]: The parser configuration.
    """
    return get_config("parser_config", parser_name)


def get_model_name_table_name(
    document_type: str,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Retrieves the output table name and model name by document type.

    Args:
        document_type (str): The document type.

    Returns:
        Tuple[Optional[str], Optional[str]]: The output table name and model name.
    """
    parser_name = get_parser_name_by_doc_type(document_type)
    if parser_name:
        parser = get_parser_by_doc_type(document_type)
        model_name = (
            f"{BQ_PROJECT_ID}.{BQ_DATASET_ID_MLOPS}."
            f"{parser.get('model_name', parser_name.upper() + '_MODEL')}"
            if parser
            else None
        )
        out_table_name = (
            f"{BQ_PROJECT_ID}.{BQ_DATASET_ID_PROCESSED_DOCS}."
            f"{parser.get('out_table_name', parser_name.upper() + '_DOCUMENTS')}"
            if parser
            else None
        )
    else:
        logger.warning(f"No parser found for document type {document_type}")
        return None, None

    logger.info(f"model_name={model_name}, out_table_name={out_table_name}")
    return model_name, out_table_name
