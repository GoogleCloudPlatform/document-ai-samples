"""
Document AI End to End Pipeline
"""
from os.path import basename as path_basename
from typing import List, Tuple

from google.api_core.exceptions import GoogleAPICallError

from consts import (
    DOCAI_PROCESSOR_LOCATION,
    DOCAI_PROJECT_ID,
    FIRESTORE_COLLECTION,
    FIRESTORE_PROJECT_ID,
)
from docai_utils import (
    classify_document_bytes,
    extract_document_entities,
    process_document_bytes,
    select_processor_from_classification,
)
from firestore_utils import save_to_firestore


def run_docai_pipeline(local_files: List[Tuple[str, str]]):
    """
    Classify Document Types,
    Select Appropriate Parser Processor,
    Extract Entities,
    Save Entities to Firestore
    """

    for file_path, mime_type in local_files:
        # Read File into Memory
        with open(file_path, "rb") as file:
            file_content = file.read()

            print("Classifying file:", file_path)
            document_classification = classify_document_bytes(
                file_content, mime_type
            )
            print("Classification:", document_classification)

            # Optional: If you want to ignore unclassified documents
            if document_classification == "other":
                print("Skipping file:", file_path)
                continue

            # Get Specialized Processor
            (
                processor_type,
                processor_id,
            ) = select_processor_from_classification(document_classification)
            print(f"Using Processor {processor_type}: {processor_id}")

            # Run Parser
            try:
                document_proto = process_document_bytes(
                    DOCAI_PROJECT_ID,
                    DOCAI_PROCESSOR_LOCATION,
                    processor_id,
                    file_content,
                    mime_type,
                )
            except GoogleAPICallError:
                print("Skipping file:", file_path)
                continue

            # Extract Entities from Document
            document_entities = extract_document_entities(document_proto)

            # Specific Classification
            # e.g. w2_2020, 1099int_2020, 1099div_2020
            document_entities["classification"] = document_classification
            # Processor Type corresponds to a Broad Category
            # e.g. Multiple W2 Years correspond to the same processor type
            document_entities[
                "broad_classification"
            ] = processor_type.removesuffix("_PROCESSOR")
            document_entities["source_file"] = path_basename(file_path)
            document_id = document_entities["broad_classification"]

            # Save Document Entities to Firestore
            print(
                f"Writing Document Entities to Firestore. \
                Document ID: {document_id}"
            )
            save_to_firestore(
                project_id=FIRESTORE_PROJECT_ID,
                collection=FIRESTORE_COLLECTION,
                document_id=document_id,
                data=document_entities,
            )
