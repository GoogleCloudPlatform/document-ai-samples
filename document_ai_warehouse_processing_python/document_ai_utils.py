from google.cloud import documentai_v1
from google.api_core.client_options import ClientOptions

import storage_utils

class document_ai_utils:

    def __init__(self, project_number: str, api_location: str,
                 document_ai_client: documentai_v1.DocumentProcessorServiceClient = None):
        self.project_number = project_number
        self.api_location = api_location

        self.document_ai_client = None


    def get_docai_client(self) -> documentai_v1.DocumentProcessorServiceClient:
        if not self.document_ai_client:
            client_options = ClientOptions(
                api_endpoint=f'{API_LOCATION}-documentai.googleapis.com'
            )
            self.document_ai_client = documentai_v1.DocumentProcessorServiceClient(client_options=client_options)
        return self.document_ai_client

    def get_parent(self) -> str:
        return self.document_ai_client.common_location_path(self.project_number, self.api_location)

    def get_processor(self, processor_id):
        # compose full name for processor
        processor_name = self.document_ai_client.processor_path(PROJECT_ID, API_LOCATION, processor_id)

        # Initialize request argument(s)
        request = documentai_v1.GetProcessorRequest(
            name=processor_name,
        )

        # Make the request
        return self.document_ai_client.get_processor(request=request)


    def process_file_from_gcs(
            self,
            processor_id: str,
            bucket_name: str, file_path: str,
            mime_type='application/pdf'
    ):
        client = self.get_docai_client()
        parent = self.get_parent()

        processor_name = f"{parent}/processors/{processor_id}"

        document_content = storage_utils.read_binary_object(bucket_name, file_path)

        document = documentai_v1.RawDocument(content=document_content, mime_type=mime_type)
        request = documentai_v1.ProcessRequest(raw_document=document, name=processor_name)

        response = client.process_document(request)
        return response.document
