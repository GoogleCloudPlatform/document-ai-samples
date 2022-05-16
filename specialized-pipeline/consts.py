"""
Global Constants
"""
from collections import defaultdict

import yaml

CONFIG_FILE_PATH = "config.yaml"


def read_yaml(file_path: str = CONFIG_FILE_PATH) -> defaultdict:
    """
    Reads a yaml file and returns a dictionary
    """
    with open(file_path, "r", encoding="utf8") as file:
        return defaultdict(yaml.safe_load(file))


def write_yaml(data: dict, file_path: str = CONFIG_FILE_PATH) -> None:
    """
    Writes a yaml file from a dictionary
    """
    with open(file_path, "w", encoding="utf8") as file:
        yaml.dump(data, file)


CONFIG = read_yaml(CONFIG_FILE_PATH)

DEFAULT_PROJECT_ID = CONFIG["project_id"]
DEFAULT_LOCATION = CONFIG["location"]

DOCUMENT_AI_PROCESSORS = CONFIG["document_ai"]

GCS_REGION = CONFIG["cloud_storage"]["region"]
GCS_INPUT_BUCKET = CONFIG["cloud_storage"]["input_bucket"]
GCS_INPUT_PREFIX = CONFIG["cloud_storage"]["input_prefix"]

GCS_OUTPUT_BUCKET = CONFIG["cloud_storage"]["output_bucket"]
GCS_OUTPUT_PREFIX = CONFIG["cloud_storage"]["output_prefix"]

GCS_SPLIT_BUCKET = CONFIG["cloud_storage"]["split_bucket"]
GCS_SPLIT_PREFIX = CONFIG["cloud_storage"]["split_prefix"]

GCS_ARCHIVE_BUCKET = CONFIG["cloud_storage"]["archive_bucket"]
GCS_ARCHIVE_PREFIX = CONFIG["cloud_storage"]["archive_prefix"]

# Based on https://cloud.google.com/document-ai/quotas
BATCH_MAX_FILES = 50
BATCH_MAX_REQUESTS = 5

SKIP_HUMAN_REVIEW = True
TIMEOUT = 300

# See https://cloud.google.com/document-ai/docs/file-types
PDF_MIME_TYPE = "application/pdf"
JSON_MIME_TYPE = "application/json"

ACCEPTED_MIME_TYPES = set(
    {
        PDF_MIME_TYPE,
        "image/jpeg",
        "image/png",
        "image/tiff",
        "image/gif",
        "image/bmp",
        "image/webp",
    }
)
