"""
Document AI Utility Functions
"""
from typing import Tuple

from google.cloud import documentai_v1 as documentai

from consts import CLASSIFIER_PROCESSOR_TYPES, DOCUMENT_SUPPORTED_PROCESSOR_TYPES, DOCAI_PROJECT_ID, DOCAI_PROCESSOR_LOCATION, DOCAI_ACTIVE_PROCESSORS, DEFAULT_MIME_TYPE

# Instantiates a client
documentai_client = documentai.DocumentProcessorServiceClient()


def process_document_bytes(project_id: str, location: str,
                           processor_id: str, file_content: bytes,
                           mime_type: str = DEFAULT_MIME_TYPE) -> documentai.Document:
    """
    Processes a document using the Document AI API.
    Takes in bytes from file reading, instead of a file path
    """

    # The full resource name of the processor, e.g.:
    # projects/project-id/locations/location/processor/processor-id
    # You must create new processors in the Cloud Console first
    resource_name = documentai_client.processor_path(
        project_id, location, processor_id)

    # Load Binary Data into Document AI RawDocument Object
    raw_document = documentai.RawDocument(
        content=file_content, mime_type=mime_type)

    # Configure the process request
    request = documentai.ProcessRequest(
        name=resource_name, raw_document=raw_document)

    # Use the Document AI client to process the sample form
    result = documentai_client.process_document(request=request)

    return result.document


def extract_data_from_entity(entity: documentai.Document.Entity, use_enriched: bool = False, use_structured_value: bool = False) -> Tuple[str, any]:
    """
    Extract Data from from Document.Entity
    Returns Tuple of (key, value)
    """

    key = entity.type_
    # some other value formats in addition to text are availible
    # e.g. dates: `entity.normalized_value.date_value.year`
    # Use EKG Enriched Data if available

    normalized_value = getattr(entity, "normalized_value", None)
    if use_enriched and normalized_value:
        # Use Structured Value if available
        structured_value = normalized_value._pb.WhichOneof('structured_value')

        if use_structured_value and structured_value:
            value = getattr(normalized_value, structured_value)
        else:
            value = normalized_value.text
    else:
        value = entity.mention_text

    return key, value


def extract_document_entities(document: documentai.Document, use_enriched: bool = False, use_structured_value: bool = False) -> dict:
    """
    Get all entities from a document and output as a dictionary
    Flattens nested entities/properties
    Format: entity.type_: entity.mention_text OR entity.normalized_value.structured_value
    """
    document_entities = {}
    for entity in document.entities:
        # Fields detected. For a full list of fields for each processor see
        # the processor documentation:
        # https://cloud.google.com/document-ai/docs/processors-list
        entity_key, entity_value = extract_data_from_entity(
            entity, use_enriched, use_structured_value)
        document_entities[entity_key] = entity_value

        # Properties are Sub-Entities
        for prop in entity.properties:
            prop_key, prop_value = extract_data_from_entity(
                prop, use_enriched, use_structured_value)
            document_entities[prop_key] = prop_value

    return document_entities


def select_processor_from_classification(document_classification: str = "other") -> Tuple[str, str]:
    """
    Select Processor for a given Document Classification
    """

    # Get Supported Parser Processor Type from Document Classification
    processor_type = DOCUMENT_SUPPORTED_PROCESSOR_TYPES.get(
        document_classification, "FORM_PARSER_PROCESSOR")

    # Get Specific Processor ID for this Parser Type
    processor_id = DOCAI_ACTIVE_PROCESSORS.get(processor_type)

    return processor_type, processor_id


def classify_document_bytes(file_content: bytes, mime_type: str) -> str:
    """
    Classify a single document with all available specialized processors
    """

    # Cycle through all possible classifier Processor Types
    for classifier_processor_type in CLASSIFIER_PROCESSOR_TYPES:
        # Get Specific Processor ID for this Classifier Type
        classifier_processor_id = DOCAI_ACTIVE_PROCESSORS.get(
            classifier_processor_type)
        if classifier_processor_id is None:
            continue

        # Classify Document
        classification_document_proto = process_document_bytes(DOCAI_PROJECT_ID,
                                                               DOCAI_PROCESSOR_LOCATION,
                                                               classifier_processor_id,
                                                               file_content,
                                                               mime_type)
        # Translate Classification Output to Processor Type
        document_classification = classification_document_proto.entities[0].type_

        # Specialized Classifiers return "other" if it could not classify to a known type
        if document_classification == "other":
            continue

    return document_classification
