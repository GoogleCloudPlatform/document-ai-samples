"""
Global Constants
"""

DEFAULT_PROJECT_ID = "pdai-sandbox"
DEFAULT_LOCATION = "us"

# Document AI
BATCH_MAX_FILES = 50
BATCH_MAX_REQUESTS = 5

TIMEOUT = 500

CUSTOM_SPLITTER_PROCESSOR = {
    "project_id": DEFAULT_PROJECT_ID,
    "location": DEFAULT_LOCATION,
    "processor_id": "fc85f5f8ff0628d2",
}

INVOICE_PARSER_PROCESSOR = {
    "project_id": DEFAULT_PROJECT_ID,
    "location": DEFAULT_LOCATION,
    "processor_id": "3a6970f87286a19c",
}

BILL_OF_LADING_PROCESSOR = {
    "project_id": DEFAULT_PROJECT_ID,
    "location": DEFAULT_LOCATION,
    "processor_id": "fc1a081baf610751",
}

# GCS
GCS_PROJECT_ID = DEFAULT_PROJECT_ID

GCS_INPUT_BUCKET = f"{GCS_PROJECT_ID}-input-invoices"
GCS_INPUT_PREFIX = "upload"

GCS_SPLIT_PREFIX = "split"

GCS_OUTPUT_BUCKET = f"{GCS_PROJECT_ID}-output-invoices"
GCS_OUTPUT_PREFIX = "processed"
DESTINATION_URI = f"gs://{GCS_OUTPUT_BUCKET}/{GCS_OUTPUT_PREFIX}/"

GCS_ARCHIVE_BUCKET = f"{GCS_PROJECT_ID}-archived-invoices"


# BigQuery
BIGQUERY_PROJECT_ID = DEFAULT_PROJECT_ID
BIGQUERY_TABLE_NAME = "doc_ai_extracted_entities"
BIGQUERY_DATASET_NAME = "invoice_parser_results"

ACCEPTED_MIME_TYPES = set(
    [
        "application/pdf",
        "image/bmp",
        "image/gif",
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/tif",
        "image/tiff",
        "image/webp",
    ]
)
