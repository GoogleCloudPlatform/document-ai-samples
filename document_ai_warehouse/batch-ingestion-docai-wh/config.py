import os

API_LOCATION = "us"  # Choose "us" or "eu"
DOCAI_WH_PROJECT_NUMBER = os.environ[
    "DOCAI_WH_PROJECT_NUMBER"
]  # Set this to your DW project number
CALLER_USER = f"user:{os.environ['CALLER_USER']}"  # service account
PROCESSOR_ID = os.environ.get("PROCESSOR_ID")  # Processor ID inside DW project
GCS_OUTPUT_BUCKET = os.environ.get(
    "DOCAI_OUTPUT_BUCKET"
)  # GCS Folder to be used for the DocAI output
DOCAI_PROJECT_NUMBER = os.environ.get(
    "DOCAI_PROJECT_NUMBER"
)  # GCS Folder to be used for the DocAI output

DOCAI_WH_PROJECT_ID = os.environ.get("DOCAI_WH_PROJECT_ID")
FOLDER_SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "schema_files/folder_schema.json"
)
DOCUMENT_SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "./schema_files/document_schema.json"
)
