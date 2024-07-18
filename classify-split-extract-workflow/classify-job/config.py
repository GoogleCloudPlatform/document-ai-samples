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

from google.cloud import run_v2, storage
import json
import os
from typing import Optional, Dict

import google.auth
from logging_handler import Logger

logger = Logger.get_logger(__file__)

# Environment variables and default settings
PROJECT_ID = os.environ.get("PROJECT_ID") or google.auth.default()[1]

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
CONFIG_FILE_NAME = "config.json"
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


CONFIG_JSON_DOCUMENT_TYPES_CONFIG = "document_types_config"
FULL_JOB_NAME = run_v2.ExecutionsClient.job_path(PROJECT_ID, REGION, "classify-job")

# Global variables
gcs = None
bucket = None
last_modified_time_of_object = None
config_data = None

logger.info(
    f"Settings used: CLASSIFY_INPUT_BUCKET=gs://{CLASSIFY_INPUT_BUCKET}, INPUT_FILE={INPUT_FILE}, "
    f"CLASSIFY_OUTPUT_BUCKET=gs://{CLASSIFY_OUTPUT_BUCKET}, OUTPUT_FILE_JSON={OUTPUT_FILE_JSON}, "
    f"OUTPUT_FILE_CSV={OUTPUT_FILE_CSV}, CALL_BACK_URL={CALL_BACK_URL}, "
    f"BQ_DATASET_ID_PROCESSED_DOCS={BQ_DATASET_ID_PROCESSED_DOCS}, BQ_DATASET_ID_MLOPS={BQ_DATASET_ID_MLOPS}, "
    f"BQ_PROJECT_ID={BQ_PROJECT_ID}, BQ_GCS_CONNECTION_NAME={BQ_GCS_CONNECTION_NAME}, "
    f"DOCAI_OUTPUT_BUCKET={DOCAI_OUTPUT_BUCKET}"
)


def init_bucket(bucket_name: str) -> None:
    """
    Initializes the GCS bucket.

    Args:
        bucket_name (str): The name of the bucket.
    """
    global gcs, bucket
    if not gcs:
        gcs = storage.Client()

    if not bucket:
        bucket = gcs.bucket(bucket_name)
        if not bucket.exists():
            logger.error(f"Bucket does not exist: gs://{bucket_name}")
            bucket = None


def get_config(config_name: Optional[str] = None, element_path: str = None) -> Optional[Dict]:
    """
    Retrieves the configuration data.

    Args:
        config_name (Optional[str]): The configuration name.
        element_path  (Optional[str]): The element path.

    Returns:
        Dict: The configuration data.
    """
    global config_data, last_modified_time_of_object
    if not config_data:
        config_data = load_config(CONFIG_BUCKET, CONFIG_FILE_NAME)
        assert config_data, "Unable to load configuration data"

    config_data_loaded = config_data.get(config_name, {}) if config_name else config_data

    if element_path:
        keys = element_path.split('.')
        for key in keys:
            if isinstance(config_data_loaded, dict):
                config_data_loaded_new = config_data_loaded.get(key)
                if config_data_loaded_new is None:
                    logger.error(f"Key '{key}' not present in the configuration {json.dumps(config_data_loaded, indent=4)}")
                    return None
                config_data_loaded = config_data_loaded_new
            else:
                logger.error(f"Expected a dictionary at '{key}' but found a {type(config_data_loaded).__name__}")
                return None

    return config_data_loaded


def get_parser_name_by_doc_type(doc_type: str) -> Optional[str]:
    return get_config(CONFIG_JSON_DOCUMENT_TYPES_CONFIG, f"{doc_type}.parser")


def get_document_types_config() -> Dict:
    return get_config(CONFIG_JSON_DOCUMENT_TYPES_CONFIG)


def get_parser_by_doc_type(doc_type: str) -> Optional[Dict]:
    parser_name = get_parser_name_by_doc_type(doc_type)
    if parser_name:
        return get_config("parser_config", parser_name)

    return None


def load_config(bucket_name: str, filename: str) -> Optional[Dict]:
    global bucket, last_modified_time_of_object, config_data

    if not bucket:
        init_bucket(bucket_name)

    if not bucket:
        return None

    blob = bucket.get_blob(filename)
    if not blob:
        logger.error(f"Error: file does not exist gs://{bucket_name}/{filename}")
        return None

    last_modified_time = blob.updated
    if last_modified_time == last_modified_time_of_object:
        return config_data

    logger.info(f"Reloading config from: {filename}")
    try:
        config_data = json.loads(blob.download_as_text(encoding="utf-8"))
        last_modified_time_of_object = last_modified_time
    except Exception as e:
        logger.error(f"Error while obtaining file from GCS gs://{bucket_name}/{filename}: {e}")
        logger.warning(f"Using local {filename}")
        try:
            with open(os.path.join(os.path.dirname(__file__), "config", filename)) as json_file:
                config_data = json.load(json_file)
        except Exception as e:
            logger.error(f"Error loading local config file {filename}: {e}")
            return None

    return config_data


def get_docai_settings() -> Dict:
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
    for k, v in get_document_types_config().items():
        if v.get("classifier_label") == label_name:
            return k
    logger.error(f"classifier_label={label_name} is not assigned to any document in the config")
    return None


def get_parser_by_name(parser_name: str) -> Optional[Dict]:
    return get_config("parser_config", parser_name)


def get_model_name_table_name(document_type: str) -> tuple[Optional[str], Optional[str]]:
    parser = get_parser_by_doc_type(document_type)
    if parser:
        parser_name = get_parser_name_by_doc_type(document_type)
        model_name = f"{BQ_PROJECT_ID}.{BQ_DATASET_ID_MLOPS}.{parser.get('model_name', parser_name.upper() + '_MODEL')}"
        out_table_name = f"{BQ_PROJECT_ID}.{BQ_DATASET_ID_PROCESSED_DOCS}." \
                         f"{parser.get('out_table_name', parser_name.upper() + '_DOCUMENTS')}"
    else:
        logger.warning(f"No parser found for document type {document_type}")
        return None, None

    logger.info(f"model_name={model_name}, out_table_name={out_table_name}")
    return model_name, out_table_name

