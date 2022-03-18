from google.cloud import documentai_v1 as documentai

project_id = "YOUR_PROJECT_ID"
location = "YOUR_PROJECT_LOCATION"  # Format is "us" or "eu"
processor_id = "YOUR_PROCESSOR_ID"  # Create processor in Cloud Console

# The local file in your current working directory
file_path = "local_file.pdf"
# Refer to https://cloud.google.com/document-ai/docs/processors-list for supported file types
mime_type = "application/pdf"

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

# Read the file into memory
with open(file_path, "rb") as image:
    image_content = image.read()

# Load Binary Data into Document AI RawDocument Object
raw_document = documentai.RawDocument(
    content=image_content, mime_type=mime_type)

# Configure the process request
request = documentai.ProcessRequest(
    name=resource_name, raw_document=raw_document)

# Use the Document AI client to process the sample form
result = docai_client.process_document(request=request)

document_object = result.document
print("Document processing complete.")
print(f"Text: {document_object.text}")
