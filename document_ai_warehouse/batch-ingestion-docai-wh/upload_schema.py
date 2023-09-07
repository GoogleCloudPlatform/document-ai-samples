import argparse

from load_docs import create_document_schema


def get_args():
    # Read command line arguments
    args_parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description="""
      Script to upload document schema into Docai WH.
      """,
        epilog="""
      Examples:

      python upload_schema.py -f=gs://my-folder/schema_name.json [-o]
      """,
    )

    args_parser.add_argument(
        "-f",
        dest="schema_path",
        help="Path to document schema json file.",
        required=True,
    )
    args_parser.add_argument(
        "-o",
        "--overwrite",
        dest="overwrite",
        help="Overwrite schema if already exists.",
        action="store_true",
        default=False,
    )
    return args_parser


def main():
    create_document_schema(schema_path, overwrite)


if __name__ == "__main__":
    parser = get_args()
    args = parser.parse_args()
    schema_path = args.schema_path
    overwrite = args.overwrite
    main()
