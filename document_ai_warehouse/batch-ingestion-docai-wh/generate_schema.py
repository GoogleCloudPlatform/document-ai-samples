import argparse
import os
import sys
from google.cloud import storage
import load_docs
sys.path.append(os.path.join(os.path.dirname(__file__), '../common/src'))

from common.utils.document_ai_utils import DocumentaiUtils
from config import API_LOCATION, PROCESSOR_ID, \
  GCS_OUTPUT_BUCKET, DOCAI_PROJECT_NUMBER

storage_client = storage.Client()

assert PROCESSOR_ID, "PROCESSOR_ID not set"
assert GCS_OUTPUT_BUCKET, "GCS_OUTPUT_BUCKET not set"
assert DOCAI_PROJECT_NUMBER, "DOCAI_PROJECT_NUMBER not set"

docai_utils = DocumentaiUtils(project_number=DOCAI_PROJECT_NUMBER,
                              api_location=API_LOCATION)


def get_args():
  # Read command line arguments
  args_parser = argparse.ArgumentParser(
      formatter_class=argparse.RawTextHelpFormatter,
      description="""
      Script to Batch load PDF data into the Document AI Warehouse.
      """,
      epilog="""
      Examples:

      python generate_schema.py -d=gs://my-folder [-n=UM_Guidelines]]
      """)

  args_parser.add_argument('-f', dest="uri",
                           help="Path to gs file uri used for DocAI parsing for schema extraction.",
                           required=True)

  return args_parser


def main(f_uri: str):
  # Process All Documents in One batch
  docai_output_list = docai_utils.batch_extraction(PROCESSOR_ID,
                                                   [f_uri],
                                                   GCS_OUTPUT_BUCKET)
  processor = docai_utils.get_processor(PROCESSOR_ID)

  for f in docai_output_list:
    document_ai_output = docai_output_list[f]
    keys = load_docs.get_key_value_pairs(document_ai_output)

    schema_path = load_docs.create_mapping_schema(processor.display_name, keys)
    print(f"Generated {schema_path} with document schema for {f_uri}")


if __name__ == "__main__":
  parser = get_args()
  args = parser.parse_args()
  uri = args.uri

  main(uri)
