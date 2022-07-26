from docai_utils import extract_subdocuments

from processor_map import PROCESSOR_SUPPORTED_DOCUMENT_TYPES
from google.cloud.documentai_v1 import Document


def main():
    splitter_output = "/Users/holtskinner/GitHub/python-documentai/samples/snippets/resources/sample_output/output_files_full/v1_processor_procurement-document-splitter_sync_full-output.json"

    with open(splitter_output, "r") as doc_json:
        doc = Document.from_json(doc_json.read())
        subdocuments = extract_subdocuments(doc)

    print(subdocuments)


main()
