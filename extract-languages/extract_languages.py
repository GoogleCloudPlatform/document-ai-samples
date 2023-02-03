"""
Detect Languages from a Document
Works with any processor that outputs "detectedLanguage"
"""
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai
import pandas as pd


def online_process(
    project_id: str,
    location: str,
    processor_id: str,
    file_path: str,
    mime_type: str,
) -> documentai.Document:
    """
    Processes a document using the Document AI Online Processing API.
    """

    documentai_client = documentai.DocumentProcessorServiceClient(
        client_options=ClientOptions(
            api_endpoint=f"{location}-documentai.googleapis.com"
        )
    )

    resource_name = documentai_client.processor_path(project_id, location, processor_id)

    with open(file_path, "rb") as file:
        file_content = file.read()

    result = documentai_client.process_document(
        request=documentai.ProcessRequest(
            name=resource_name,
            raw_document=documentai.RawDocument(
                content=file_content, mime_type=mime_type
            ),
        )
    )

    return result.document


PROJECT_ID = "YOUR_PROJECT_ID"
LOCATION = "us"  # Format is 'us' or 'eu'
PROCESSOR_ID = "YOUR_PROCESSOR_ID"  # Create processor in Cloud Console

FILE_PATH = "multi_language.pdf"
MIME_TYPE = "application/pdf"

document = online_process(
    project_id=PROJECT_ID,
    location=LOCATION,
    processor_id=PROCESSOR_ID,
    file_path=FILE_PATH,
    mime_type=MIME_TYPE,
)

print("Document processing complete.")

extracted_languages = []

for page in document.pages:
    for language in page.detected_languages:
        extracted_languages.append(
            {
                "page_number": page.page_number,
                "language_code": language.language_code,
                "confidence": f"{language.confidence:.0%}",
            }
        )

# Create a Pandas Dataframe to print the values in tabular format.
df = pd.DataFrame(extracted_languages)

print(df)
