"""
Global Constants
"""

DEFAULT_PROJECT_ID = "pdai-sandbox"
DEFAULT_LOCATION = "us"

# Document AI
BATCH_MAX_FILES = 50
BATCH_MAX_REQUESTS = 5

TIMEOUT = 200

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

# Map of Document Classification to Processor
DOCUMENT_PROCESSOR_MAP = {
    "airway_bill": INVOICE_PARSER_PROCESSOR,
    "commercial_invoice": INVOICE_PARSER_PROCESSOR,
    "importer_security_filing": INVOICE_PARSER_PROCESSOR,
    "invoice_logistics": INVOICE_PARSER_PROCESSOR,
    "invoice_statement": INVOICE_PARSER_PROCESSOR,
    "packing_list": INVOICE_PARSER_PROCESSOR,
    "seaway_bill": INVOICE_PARSER_PROCESSOR,
    "tax_invoice": INVOICE_PARSER_PROCESSOR,
    "other": INVOICE_PARSER_PROCESSOR,
    "bill_of_lading": BILL_OF_LADING_PROCESSOR,
    "bill_of_lading_supplement": BILL_OF_LADING_PROCESSOR,
}

# GCS
GCS_PROJECT_ID = DEFAULT_PROJECT_ID

# GCS_INPUT_BUCKET = f"{GCS_PROJECT_ID}-input-invoices"
# GCS_INPUT_PREFIX = "upload"

GCS_INPUT_BUCKET = "pdai-sandbox-input-invoices"
GCS_INPUT_PREFIX = "upload"

GCS_SPLIT_BUCKET = f"{GCS_PROJECT_ID}-split-invoices"
GCS_SPLIT_PREFIX = "split"

GCS_OUTPUT_BUCKET = f"{GCS_PROJECT_ID}-output-invoices"
GCS_OUTPUT_PREFIX = "processed"
DESTINATION_URI = f"gs://{GCS_OUTPUT_BUCKET}/{GCS_OUTPUT_PREFIX}/"

GCS_ARCHIVE_BUCKET = f"{GCS_PROJECT_ID}-archived-invoices"


# BigQuery
BIGQUERY_PROJECT_ID = DEFAULT_PROJECT_ID
BIGQUERY_DATASET_NAME = "dspa_invoices_uptrained"
BIGQUERY_TABLE_NAME = "dspa_extracted_entities"

PDF_MIME_TYPE = "application/pdf"
ACCEPTED_MIME_TYPES = set({PDF_MIME_TYPE})

# ACCEPTED_MIME_TYPES = set(
#     [
#         "application/pdf",
#         "image/bmp",
#         "image/gif",
#         "image/jpeg",
#         "image/jpg",
#         "image/png",
#         "image/tif",
#         "image/tiff",
#         "image/webp",
#     ]
# )
