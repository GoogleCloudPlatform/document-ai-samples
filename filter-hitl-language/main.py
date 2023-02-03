"""
Detect Languages from a Document
Works with any processor that outputs "detectedLanguage"
"""

from docai_utils import sort_document_files_by_language

PROJECT_ID = "YOUR PROJECT ID"

# Output Files from Human-in-the-loop
GCS_HITL_BUCKET = "input-bucket"
GCS_HITL_PREFIX = "input-directory"

# Output Bucket names will be in the format of GCS_OUTPUT_BUCKET_PREFIX + language
GCS_OUTPUT_BUCKET_PREFIX = "output-bucket-"


sort_document_files_by_language(
    GCS_HITL_BUCKET, GCS_HITL_PREFIX, GCS_OUTPUT_BUCKET_PREFIX
)
