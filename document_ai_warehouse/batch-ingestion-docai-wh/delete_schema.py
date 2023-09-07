import argparse

from load_docs import delete_schema
from load_docs import delete_schema_by_name


def get_args():
    # Read command line arguments
    args_parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description="""
      Script to delete document schema into Docai WH.
      """,
        epilog="""
      Examples:

      python delete_schema.py -s=schema_id
      """,
    )

    args_parser.add_argument(
        "-s",
        dest="schema_id",
        action="append",
        default=[],
        help="schema_id to be deleted.",
    )
    args_parser.add_argument(
        "-sn",
        dest="schema_name",
        action="append",
        default=[],
        help="schema display_name to be deleted.",
    )

    return args_parser


def main():
    delete_schema(schema_id)


if __name__ == "__main__":
    parser = get_args()
    args = parser.parse_args()
    schema_ids = args.schema_id
    schema_names = args.schema_name

    if len(schema_ids) > 0:
        for schema_id in schema_ids:
            delete_schema(schema_id)
    if len(schema_names) > 0:
        for schema_name in schema_names:
            delete_schema_by_name(schema_name)
