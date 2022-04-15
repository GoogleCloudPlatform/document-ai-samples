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

"""This module defines a CLI that uses Document AI to classify and parse multiple PDF documents"""

import argparse
import os
import sys

import google.auth
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai

DEFAULT_MULTI_REGION_LOCATION = "us"
DEFAULT_PROCESSOR_TYPE = "DOCUMENT_SPLIT_PROCESSOR"


def main(args: argparse.Namespace) -> int:
    """Defines CLI for the Document AI pipeline."""

    if not args.project_id:
        _, project_id = google.auth.default()
        args.project_id = project_id

    if not os.path.isfile(os.path.abspath(args.input)):
        print(f"could not find file at {os.path.abspath(args.input)}")
        return 1
    if not args.output_dir:
        args.output_dir = os.path.dirname(os.path.abspath(args.input))

    client_options = ClientOptions(
        api_endpoint=f"{args.multi_region_location}-documentai.googleapis.com"
    )

    documentai_client = documentai.DocumentProcessorServiceClient(
        client_options=client_options
    )

    print(
        "Using:\n"
        f'* Project ID: "{args.project_id}"\n'
        f'* Location: "{args.multi_region_location}"\n'
        f'* Processor ID "{processor_id}"\n'
        f'* Input PDF "{os.path.basename(os.path.abspath(args.input))}"\n'
        f'* Output directory: "{args.output_dir}"\n'
    )

    # Call the specified processors process document API with the contents of
    # the input PDF file as input.
    with open(args.input, "rb") as pdf_file:
        document = client.process_document(
            request={
                "name": f"{parent}/processors/{processor_id}",
                "raw_document": {
                    "content": pdf_file.read(),
                    "mime_type": "application/pdf",
                },
            }
        ).document
    print("Done.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Split a PDF document.")
    parser.add_argument(
        "-i", "--input", help="filepath of input PDF to split", required=True
    )
    parser.add_argument(
        "--output-dir",
        help="directory to save subdocuments, default: input PDF directory",
    )
    parser.add_argument(
        "--project-id", help="Project ID to use to call the Document AI API"
    )
    parser.add_argument(
        "--multi-region-location",
        help="multi-regional location for document storage and processing",
        default=DEFAULT_MULTI_REGION_LOCATION,
    )
    parser.add_argument(
        "--split-processor-type",
        help='type of split processor e.g. "LENDING_DOCUMENT_SPLIT_PROCESSOR"',
        default=DEFAULT_PROCESSOR_TYPE,
    )
    sys.exit(main(parser.parse_args()))
