import argparse
import os
import sys

from config import API_LOCATION
from config import DOCAI_PROJECT_NUMBER
from config import GCS_OUTPUT_BUCKET
from config import PROCESSOR_ID
from google.cloud import storage
import load_docs

sys.path.append(os.path.join(os.path.dirname(__file__), "../common/src"))
from common.utils.document_ai_utils import DocumentaiUtils

storage_client = storage.Client()

assert PROCESSOR_ID, "PROCESSOR_ID not set"
assert GCS_OUTPUT_BUCKET, "GCS_OUTPUT_BUCKET not set"
assert DOCAI_PROJECT_NUMBER, "DOCAI_PROJECT_NUMBER not set"

docai_utils = DocumentaiUtils(
    project_number=DOCAI_PROJECT_NUMBER, api_location=API_LOCATION
)


def get_args():
    # Read command line arguments
    args_parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description="""
      Script to Generate and save locally document schema for DocAI Warehouse based on the DocAI output.
      """,
        epilog="""
      Examples:

      python generate_schema.py -d=gs://my-folder [-sn=schema_name]
      """,
    )

    args_parser.add_argument(
        "-f",
        dest="uri",
        help="Path to gs file uri used for DocAI parsing for schema extraction.",
        required=True,
    )
    args_parser.add_argument(
        "-sn",
        dest="schema_name",
        help="When specified, schema display name. Otherwise will use processor display name.",
    )

    return args_parser


def main(f_uri: str, schema_name: str):
    # Process All Documents in One batch

    docai_output_list = docai_utils.batch_extraction(
        PROCESSOR_ID, [f_uri], GCS_OUTPUT_BUCKET
    )
    processor = docai_utils.get_processor(PROCESSOR_ID)

    for f in docai_output_list:
        document_ai_output = docai_output_list[f]
        keys = load_docs.get_key_value_pairs(document_ai_output)

        if not schema_name:
            schema_name = processor.display_name
        schema_path = load_docs.create_mapping_schema(schema_name, keys)
        print(f"Generated {schema_path} with document schema for {f_uri}")


if __name__ == "__main__":
    parser = get_args()
    args = parser.parse_args()
    uri = args.uri
    schema_name = args.schema_name

    main(uri, schema_name)
