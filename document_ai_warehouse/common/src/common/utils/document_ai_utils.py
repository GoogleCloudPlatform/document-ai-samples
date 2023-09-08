import json
import re
import time
from typing import Any, Dict, List

from common.utils.logging_handler import Logger
from common.utils.storage_utils import read_binary_object
from common.utils.storage_utils import split_uri_2_bucket_prefix
from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import InternalServerError
from google.api_core.exceptions import RetryError
from google.cloud import documentai
from google.cloud import storage

PDF_MIME_TYPE = "application/pdf"

storage_client = storage.Client()


class DocumentaiUtils:
    def __init__(self, project_number: str, api_location: str):
        self.project_number = project_number
        self.api_location = api_location
        self.document_ai_client = None

    def get_docai_client(self) -> documentai.DocumentProcessorServiceClient:
        if not self.document_ai_client:
            client_options = ClientOptions(
                api_endpoint=f"{self.api_location}-documentai.googleapis.com"
            )
            self.document_ai_client = documentai.DocumentProcessorServiceClient(
                client_options=client_options
            )
        return self.document_ai_client

    def get_parent(self) -> str:
        client = self.get_docai_client()
        return client.common_location_path(self.project_number, self.api_location)

    def get_processor(self, processor_id: str):
        # Initialize client if not initialized yet
        client = self.get_docai_client()

        # compose full name for processor
        processor_name = client.processor_path(
            self.project_number, self.api_location, processor_id
        )
        # Initialize request argument(s)
        request = documentai.GetProcessorRequest(
            name=processor_name,
        )

        # Make the request
        return self.document_ai_client.get_processor(request=request)

    def process_file_from_gcs(
        self,
        processor_id: str,
        bucket_name: str,
        file_path: str,
        mime_type: str = "application/pdf",
    ) -> documentai.Document:
        client = self.get_docai_client()
        parent = self.get_parent()

        processor_name = f"{parent}/processors/{processor_id}"

        document_content = read_binary_object(bucket_name, file_path)

        document = documentai.RawDocument(
            content=document_content, mime_type=mime_type
        )
        request = documentai.ProcessRequest(
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

    def batch_extraction(
        self,
        processor_id: str,
        input_uris: List[str],
        gcs_output_bucket: str,
        timeout=600,
    ):
        if len(input_uris) == 0:
            return []
        client = self.get_docai_client()
        parent = self.get_parent()

        name = f"{parent}/processors/{processor_id}"
        Logger.info(f"batch_extraction - processor name = {name}")
        processor = client.get_processor(name=name)
        input_docs = [
            documentai.GcsDocument(gcs_uri=doc_uri, mime_type=PDF_MIME_TYPE)
            for doc_uri in list(input_uris)
        ]
        gcs_documents = documentai.GcsDocuments(documents=input_docs)
        input_config = documentai.BatchDocumentsInputConfig(gcs_documents=gcs_documents)

        # create a temp folder to store parser op, delete folder once processing done
        # call create gcs bucket function to create bucket,
        # folder will be created automatically not the bucket
        destination_uri = f"gs://{gcs_output_bucket}/"

        output_config = documentai.DocumentOutputConfig(
            gcs_output_config={"gcs_uri": destination_uri}
        )

        Logger.info(f"batch_extraction - input_config = {input_config}")
        Logger.info(f"batch_extraction - output_config = {output_config}")
        Logger.info(
            f"batch_extraction - Calling Processor API for {len(input_uris)} document(s) "
            f"batch_extraction - Calling DocAI API for {len(input_uris)} document(s) "
            f" using {processor.display_name} processor "
            f"type={processor.type_}, path={processor.name}"
        )

        start = time.time()
        # request for Doc AI
        request = documentai.types.document_processor_service.BatchProcessRequest(
            name=processor.name,
            input_documents=input_config,
            document_output_config=output_config,
        )
        operation = client.batch_process_documents(request)

        # Continually polls the operation until it is complete.
        # This could take some time for larger files
        # Format: projects/PROJECT_NUMBER/locations/LOCATION/operations/OPERATION_ID
        try:
            Logger.info(
                f"batch_extraction - Waiting for operation {operation.operation.name} to complete..."
            )
            operation.result(timeout=timeout)
        # Catch exception when operation doesn't finish before timeout
        except (RetryError, InternalServerError) as e:
            Logger.error(e.message)
            Logger.error("batch_extraction - Failed to process documents")
            return [], False

        elapsed = "{:.0f}".format(time.time() - start)
        Logger.info(f"batch_extraction - Elapsed time for operation {elapsed} seconds")

        # Once the operation is complete,
        # get output document information from operation metadata
        metadata = documentai.BatchProcessMetadata(operation.metadata)
        if metadata.state != documentai.BatchProcessMetadata.State.SUCCEEDED:
            raise ValueError(
                f"batch_extraction - Batch Process Failed: {metadata.state_message}"
            )

        documents = (
            {}
        )  # Contains per processed document, keys are path to original document

        # One process per Input Document
        for process in metadata.individual_process_statuses:
            # output_gcs_destination format: gs://BUCKET/PREFIX/OPERATION_NUMBER/INPUT_FILE_NUMBER/
            # The Cloud Storage API requires the bucket name and URI prefix separately
            input_gcs_source = process.input_gcs_source
            matches = re.match(r"gs://(.*?)/(.*)", process.output_gcs_destination)
            if not matches:
                Logger.error(
                    f"batch_extraction - Could not parse output GCS destination:"
                    f"[{process.output_gcs_destination}] for {input_gcs_source}"
                )
                Logger.error(f"batch_extraction - {process.status}")
                continue

            output_bucket, output_prefix = matches.groups()
            output_gcs_destination = process.output_gcs_destination

            Logger.info(
                f"batch_extraction - Handling DocAI results for {input_gcs_source} using "
                f"process output {output_gcs_destination}"
            )
            # Get List of Document Objects from the Output Bucket
            output_blobs = storage_client.list_blobs(
                output_bucket, prefix=output_prefix + "/"
            )

            # Document AI may output multiple JSON files per source file
            # Sharding happens when the output JSON File gets over a size threshold,
            # like 10MB or something. I have seen it happen around 30 pages, but more
            # often around 40 or 50 pages.
            for blob in output_blobs:
                # Document AI should only output JSON files to GCS
                if ".json" not in blob.name:
                    Logger.warning(
                        f"batch_extraction - Skipping non-supported file: {blob.name} - Mimetype: {blob.content_type}"
                    )
                    continue

                if input_gcs_source not in documents.keys():
                    documents[input_gcs_source] = []
                documents[input_gcs_source].append(f"gs://{output_bucket}/{blob.name}")

        result = {}
        for doc in documents:
            result[doc] = merge_json_files(documents[doc])

        return result


def merge_json_files(files):
    """Merges n json files in memory.

    Args:
      files: A list of paths to json files.

    Returns:
      A dictionary containing the merged data.
    """

    result = {}
    json_list = []

    for file in files:
        bucket_name, prefix = split_uri_2_bucket_prefix(file)
        bucket = storage_client.get_bucket(bucket_name)
        blob = bucket.blob(prefix)
        json_str = blob.download_as_string()
        json_list.append(json.loads(json_str.decode("utf8")))

    for d in json_list:
        result.update(d)

    doc_json = json.dumps(result)

    document = documentai.Document.from_json(doc_json, ignore_unknown_fields=True)
    return document


# Handling Nested labels for CDE processor
def get_key_values_dic(
    entity: documentai.Document.Entity,
    document_entities: Dict[str, Any],
    parent_key: str = None,
) -> None:
    # Fields detected. For a full list of fields for each processor see
    # the processor documentation:
    # https://cloud.google.com/document-ai/docs/processors-list

    entity_key = entity.get("type", "").replace("/", "_")
    confidence = entity.get("confidence")
    normalized_value = entity.get("normalizedValue")

    if normalized_value:
        if (
            isinstance(normalized_value, dict)
            and "booleanValue" in normalized_value.keys()
        ):
            normalized_value = normalized_value.get("booleanValue")
        else:
            normalized_value = normalized_value.get("text")

    if parent_key is not None and parent_key in document_entities.keys():
        key = parent_key
        new_entity_value = (
            entity_key,
            normalized_value
            if normalized_value is not None
            else entity.get("mentionText"),
            confidence,
        )
    else:
        key = entity_key
        new_entity_value = (
            normalized_value
            if normalized_value is not None
            else entity.get("mentionText"),
            confidence,
        )

    existing_entity = document_entities.get(key)
    if not existing_entity:
        document_entities[key] = []
        existing_entity = document_entities.get(key)

    if len(entity.get("properties", [])) > 0:
        # Sub-labels (only down one level)
        for prop in entity.get("properties", []):
            get_key_values_dic(prop, document_entities, entity_key)
    else:
        existing_entity.append(new_entity_value)
