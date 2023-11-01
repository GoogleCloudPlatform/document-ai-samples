# Copyright 2022 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Document AI End to End Pipeline"""

from os.path import basename as path_basename
from typing import List, Tuple

from consts import DOCAI_PROCESSOR_LOCATION
from consts import DOCAI_PROJECT_ID
from consts import FIRESTORE_PROJECT_ID
from docai_utils import classify_document
from docai_utils import extract_document_entities
from docai_utils import process_document
from docai_utils import select_processor_from_classification
from firestore_utils import save_to_firestore
from google.api_core.exceptions import GoogleAPICallError


def run_docai_pipeline(
    local_files: List[Tuple[str, str]], firestore_collection: str
) -> List[str]:
    """
    Classify Document Types,
    Select Appropriate Parser Processor,
    Extract Entities,
    Save Entities to Firestore
    """

    status_messages: List[str] = []

    def progress_update(message: str):
        """
        Print progress update to stdout and add to message queue
        """
        print(message)
        status_messages.append(message)

    for file_path, mime_type in local_files:
        file_name = path_basename(file_path)

        progress_update(f"Processing {file_name}")
        # Read File into Memory
        with open(file_path, "rb") as file:
            file_content = file.read()

        document_classification = classify_document(file_content, mime_type)

        progress_update(f"\tClassification: {document_classification}")

        # Optional: If you want to ignore unclassified documents
        if document_classification == "other":
            progress_update(f"\tSkipping file: {file_name}")
            continue

        # Get Specialized Processor
        (
            processor_type,
            processor_id,
        ) = select_processor_from_classification(document_classification)

        progress_update(f"\tUsing Processor {processor_type}: {processor_id}")

        # Run Parser
        try:
            document_proto = process_document(
                DOCAI_PROJECT_ID,
                DOCAI_PROCESSOR_LOCATION,
                processor_id,
                file_content=file_content,
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
        document_entities["broad_classification"] = processor_type.removesuffix(
            "_PROCESSOR"
        )
        document_entities["source_file"] = file_name
        document_id = document_entities["broad_classification"]

        # Save Document Entities to Firestore
        progress_update(f"\tWriting to Firestore Collection {firestore_collection}")
        progress_update(f"\tDocument ID: {document_id}")
        save_to_firestore(
            project_id=FIRESTORE_PROJECT_ID,
            collection=firestore_collection,
            document_id=document_id,
            data=document_entities,
        )

    return status_messages
