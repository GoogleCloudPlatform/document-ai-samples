"""
Global Constants
"""

PROJECT_ID = "PROJECT_ID"
LOCATION = "us"
PROCESSOR_ID = "PROCESSOR_ID"

BATCH_MAX_FILES = 50
BATCH_MAX_REQUESTS = 5

TIMEOUT = 400

# GCS Variables
gcs_input_bucket = f"{PROJECT_ID}-input-invoices"
gcs_output_bucket = f"{PROJECT_ID}-output-invoices"
gcs_archive_bucket_name = f"{PROJECT_ID}-archived-invoices"

# pylint: disable=invalid-name
gcs_output_prefix = "processed"
destination_uri = f"gs://{gcs_output_bucket}/{gcs_output_prefix}/"

# BigQuery Variables
DATSET_NAME = "invoice_parser_results"
ENTITIES_TABLE_NAME = "doc_ai_extracted_entities"

ACCEPTED_MIME_TYPES = set(
    ["application/pdf", "image/jpeg", "image/png", "image/tiff", "image/gif"]
)
