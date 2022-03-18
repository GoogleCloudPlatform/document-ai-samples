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


project_id = 'YOUR_PROJECT_ID'
location = 'YOUR_PROJECT_LOCATION'  # Format is 'us' or 'eu'
processor_id = 'INVOICE_PARSER_ID'  # Create processor in Cloud Console

# The local file in your current working directory
file_path = 'google_invoice.pdf'
# Refer to https://cloud.google.com/document-ai/docs/processors-list for supported file types
mime_type = 'application/pdf'

document = online_process(project_id=project_id, location=location,
                          processor_id=processor_id, file_path=file_path,
                          mime_type=mime_type)

types = []
raw_values = []
normalized_values = []
confidence = []

# Grab each key/value pair and their corresponding confidence scores.
for entity in document.entities:
    types.append(entity.type_)
    raw_values.append(entity.mention_text)
    normalized_values.append(entity.normalized_value.text)
    confidence.append(round(entity.confidence, 4))

    # Get Properties (Sub-Entities) with confidence scores
    for prop in entity.properties:
        types.append(prop.type_)
        raw_values.append(prop.mention_text)
        normalized_values.append(prop.normalized_value.text)
        confidence.append(round(prop.confidence, 4))

# Create a Pandas Dataframe to print the values in tabular format.
df = pd.DataFrame({'Type': types, 'Raw Value': raw_values,
                  'Normalized Value': normalized_values, 'Confidence': confidence})

print(df)
