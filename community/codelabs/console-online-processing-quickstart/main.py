"""
Create OCR Processor
Make Online Processing Request to Document AI
"""
import os

from google.api_core.client_options import ClientOptions
from google.cloud import documentai

# TODO(developer): Update these variables before running the sample.
PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
# Format is 'us' or 'eu'
LOCATION = "us"

# Must be unique per project, e.g.: 'my-processor'
PROCESSOR_DISPLAY_NAME = "my-processor"
PROCESSOR_TYPE = "OCR_PROCESSOR"

FILE_PATH = "Winnie_the_Pooh_3_Pages.pdf"
# Refer to https://cloud.google.com/document-ai/docs/file-types for supported file types
MIME_TYPE = "application/pdf"
# Optional. The fields to return in the Document object.
FIELD_MASK = "text,entities,pages.pageNumber"

if __name__ == "__main__":
    # You must set the api_endpoint if you use a location other than 'us', e.g.:
    opts = ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")

    # Create Document AI Client
    client = documentai.DocumentProcessorServiceClient(client_options=opts)

    # The full resource name of the location
    # e.g.: projects/project_id/locations/location
    parent = client.common_location_path(PROJECT_ID, LOCATION)

    # Create a processor
    processor = client.create_processor(
        parent=parent,
        processor=documentai.Processor(
            display_name=PROCESSOR_DISPLAY_NAME, type_=PROCESSOR_TYPE
        ),
    )

    # Print the processor information
    print("Created New Processor")
    print("---------------------")
    print(f"Name: {processor.name}")
    print(f"Display Name: {processor.display_name}")
    print(f"Type: {processor.type_}\n")

    print(f"Extracting Text from {FILE_PATH}\n")
    # Read the file into memory
    with open(FILE_PATH, "rb") as image:
        image_content = image.read()

    # Load Binary Data into Document AI RawDocument Object
    raw_document = documentai.RawDocument(content=image_content, mime_type=MIME_TYPE)

    # Configure the process request
    request = documentai.ProcessRequest(
        name=processor.name, raw_document=raw_document, field_mask=FIELD_MASK
    )

    # Use the Document AI client to process the sample document
    result = client.process_document(request=request)

    # For a full list of Document object attributes, please reference this page:
    # https://cloud.google.com/python/docs/reference/documentai/latest/google.cloud.documentai_v1.types.Document
    document = result.document

    # Read the text recognition output from the processor
    print("The document contains the following text:")
    print(document.text)
