"""
Global Constants
"""

PROJECT_ID = "pdai-sandbox"
LOCATION = "us"
PROCESSOR_ID = "3a6970f87286a19c"

BATCH_MAX_FILES = 50
BATCH_MAX_REQUESTS = 5

TIMEOUT = 500

# GCS Variables
gcs_input_bucket = f"{PROJECT_ID}-input-invoices"
gcs_input_prefix = ""

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
