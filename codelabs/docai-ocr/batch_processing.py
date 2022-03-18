import re

from google.api_core.operation import Operation
from google.cloud import documentai_v1 as documentai
from google.cloud import storage
from typing import List


def get_documents_from_gcs(
    gcs_output_uri: str, operation_name: str
) -> List[documentai.Document]:
    """
    Download the document output from GCS.
    """

    # The GCS API requires the bucket name and URI prefix separately
    match = re.match(r"gs://([^/]+)/(.+)", gcs_output_uri)
    output_bucket = match.group(1)
    prefix = match.group(2)

    # The output files will be in a new subdirectory with the Operation ID as the name
    operation_id = re.search(
        "operations\/(\d+)", operation_name, re.IGNORECASE).group(1)

    output_directory = f"{prefix}/{operation_id}"

    storage_client = storage.Client()

    # List of all of the files in the directory `gs://gcs_output_uri/operation_id`
    blob_list = list(storage_client.list_blobs(
        output_bucket, prefix=output_directory))

    output_documents = []

    for blob in blob_list:
        # Document AI should only output JSON files to GCS
        if ".json" in blob.name:
            document = documentai.types.Document.from_json(
                blob.download_as_bytes())
            output_documents.append(document)
        else:
            print(f"Skipping non-supported file type {blob.name}")

    return output_documents


project_id = 'YOUR_PROJECT_ID'
location = 'YOUR_PROJECT_LOCATION'  # Format is 'us' or 'eu'
processor_id = 'YOUR_PROCESSOR_ID'  # Create processor in Cloud Console

# Format 'gs://input_bucket/directory/file.pdf'
gcs_input_uri = "INPUT_BUCKET_URI"
input_mime_type = "application/pdf"

# Format 'gs://output_bucket/directory'
gcs_output_uri = "YOUR_OUTPUT_BUCKET_URI"

opts = {
    "api_endpoint": f"{location}-documentai.googleapis.com"
}

# Instantiates a client
docai_client = documentai.DocumentProcessorServiceClient(
    client_options=opts)

# The full resource name of the processor, e.g.:
# projects/project-id/locations/location/processor/processor-id
# You must create new processors in the Cloud Console first
resource_name = docai_client.processor_path(project_id, location, processor_id)

# Cloud Storage URI for the Input Document
input_document = documentai.GcsDocument(
    gcs_uri=gcs_input_uri, mime_type=input_mime_type
)

# Load GCS Input URI into a List of document files
input_config = documentai.BatchDocumentsInputConfig(
    gcs_documents=documentai.GcsDocuments(documents=[input_document])
)

# Cloud Storage URI for Output directory
gcs_output_config = documentai.DocumentOutputConfig.GcsOutputConfig(
    gcs_uri=gcs_output_uri
)

# Load GCS Output URI into OutputConfig object
output_config = documentai.DocumentOutputConfig(
    gcs_output_config=gcs_output_config)

# Configure Process Request
request = documentai.BatchProcessRequest(
    name=resource_name,
    input_documents=input_config,
    document_output_config=output_config,
)

# Batch Process returns a Long Running Operation (LRO)
operation = docai_client.batch_process_documents(request)

# Format: projects/PROJECT_NUMBER/locations/LOCATION/operations/OPERATION_ID
operation_name = operation.operation.name

# Continually polls the operation until it is complete.
# This could take some time for larger files
print(f"Waiting for operation {operation_name} to complete...")
result = operation.result(timeout=300)

# NOTE: Can also use callbacks for asynchronous processing
#
# def my_callback(future):
#   result = future.result()
#
# operation.add_done_callback(my_callback)

print("Document processing complete.")

# Get the Document Objects from the Output Bucket
document_list = get_documents_from_gcs(
    gcs_output_uri=gcs_output_uri, operation_name=operation_name
)

for document in document_list:
    print(document.text)
