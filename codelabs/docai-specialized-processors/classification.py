from google.cloud import documentai_v1 as documentai
import pandas as pd


def online_process(project_id: str, location: str,
                   processor_id: str, file_path: str,
                   mime_type: str) -> documentai.Document:
    """
    Processes a document using the Document AI Online Processing API.
    """

    opts = {
        "api_endpoint": f"{location}-documentai.googleapis.com"
    }

    # Instantiates a client
    documentai_client = documentai.DocumentProcessorServiceClient(
        client_options=opts)

    # The full resource name of the processor, e.g.:
    # projects/project-id/locations/location/processor/processor-id
    # You must create new processors in the Cloud Console first
    resource_name = documentai_client.processor_path(
        project_id, location, processor_id)

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
        result = documentai_client.process_document(request=request)

        return result.document


project_id = 'document-ai-test-337818'
location = 'us'
processor_id = 'a95d5474021fc9ee'

file_path = 'procurement_multi_document.pdf'
mime_type = 'application/pdf'

# project_id = 'YOUR_PROJECT_ID'
# location = 'YOUR_PROJECT_LOCATION'  # Format is 'us' or 'eu'
# processor_id = 'PROCUREMENT_SPLITTER_ID'  # Create processor in Cloud Console

# # The local file in your current working directory
# file_path = 'procurement_multi_document.pdf'
# # Refer to https://cloud.google.com/document-ai/docs/processors-list for supported file types
# mime_type = 'application/pdf'

document = online_process(project_id=project_id, location=location,
                          processor_id=processor_id, file_path=file_path,
                          mime_type=mime_type)

print("Document processing complete.")

types = []
confidence = []
pages = []

# Each Document.entity is a classification
for entity in document.entities:
    classification = entity.type_
    types.append(classification)
    confidence.append(entity.confidence)

    # entity.page_ref contains the pages that match the classification
    pages_list = []
    for page_ref in entity.page_anchor.page_refs:
        pages_list.append(page_ref.page)
    pages.append(pages_list)

df = pd.DataFrame({'Classification': types,
                   'Confidence': confidence,
                   'Pages': pages})

print(df)
