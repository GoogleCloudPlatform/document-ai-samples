from google.cloud import documentai_v1
from google.api_core.client_options import ClientOptions
import storage_utils


class DocumentaiUtils:
    def __init__(self, project_number: str, api_location: str):
        self.project_number = project_number
        self.api_location = api_location
        self.document_ai_client = None

    def get_docai_client(self) -> documentai_v1.DocumentProcessorServiceClient:
        if not self.document_ai_client:
            client_options = ClientOptions(
                api_endpoint=f"{self.api_location}-documentai.googleapis.com"
            )
            self.document_ai_client = documentai_v1.DocumentProcessorServiceClient(
                client_options=client_options
            )
        return self.document_ai_client

    def get_parent(self) -> str:
        client = self.get_docai_client()
        return client.common_location_path(self.project_number, self.api_location)

    def get_processor(self, processor_id):
        # compose full name for processor
        processor_name = self.document_ai_client.processor_path(
            self.project_number, self.api_location, processor_id
        )
        # Initialize request argument(s)
        request = documentai_v1.GetProcessorRequest(
            name=processor_name,
        )

        # Make the request
        return self.document_ai_client.get_processor(request=request)

    def process_file_from_gcs(
        self,
        processor_id: str,
        bucket_name: str,
        file_path: str,
        mime_type="application/pdf",
    ):
        client = self.get_docai_client()
        parent = self.get_parent()

        processor_name = f"{parent}/processors/{processor_id}"

        document_content = storage_utils.read_binary_object(bucket_name, file_path)

        document = documentai_v1.RawDocument(
            content=document_content, mime_type=mime_type
        )
        request = documentai_v1.ProcessRequest(
            raw_document=document, name=processor_name
        )

        response = client.process_document(request)

        return response.document

    @staticmethod
    def get_entity_key_value_pairs(docai_document):
        fields = {}
        if hasattr(docai_document, "entities"):
            entities = {}
            for entity in docai_document.entities:
                key = entity.type_
                value = entity.mention_text
                if key not in entities:
                    entities[key] = []
                entities[key].append(value)

            for key in entities:
                values = entities[key]
                N = len(values)

                for i in range(N):
                    if i == 0:
                        fields[key] = values[i]
                    else:
                        fields[key + "_" + str(i + 1)] = values[i]

        return fields
