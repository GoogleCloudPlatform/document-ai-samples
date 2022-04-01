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

"""This module defines a CLI that uses Document AI to split a PDF document"""

import argparse
import os
import sys
from typing import Optional

import google.auth
from google.cloud.documentai_v1beta3 import (DocumentProcessorServiceClient,
                                             Processor)
from pikepdf import Pdf

DEFAULT_MULTI_REGION_LOCATION = "us"
DEFAULT_PROCESSOR_TYPE = "DOCUMENT_SPLIT_PROCESSOR"


def main(args: argparse.Namespace) -> int:
    """This functions splits a PDF document using the Document AI API"""
    if not args.project_id:
        _, project_id = google.auth.default()
        args.project_id = project_id
    parent = f"projects/{args.project_id}/locations/{args.multi_region_location}"
    client = DocumentProcessorServiceClient()

    processor_id = find_processor_id_of_type(client, parent, args.split_processor_type)
    if processor_id is None:
        print(
            f"no split processor found. "
            f'creating new processor of type "{args.split_processor_type}"',
        )
        processor_id = create_processor(client, parent, args.split_processor_type)

    if not os.path.isfile(os.path.abspath(args.input)):
        print(f"could not find file at {os.path.abspath(args.input)}")
        return 1
    if not args.output_dir:
        args.output_dir = os.path.dirname(os.path.abspath(args.input))

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

    with Pdf.open(os.path.abspath(args.input)) as original_pdf:
        for index, entity in enumerate(document.entities):
            print(
                f"Creating subdocument {str(index + 1)} of {str(len(document.entities))}."
            )

            start = int(entity.page_anchor.page_refs[0].page)
            try:
                end = int(entity.page_anchor.page_refs[1].page)
            except IndexError:
                end = start

            subdoc = Pdf.new()
            for page_num in range(start, end + 1):
                subdoc.pages.append(original_pdf.pages[page_num])

            subdoc.save(
                os.path.join(
                    args.output_dir,
                    f"subdoc_{str(index + 1)}_of_{str(len(document.entities))}_"
                    f"{os.path.basename(os.path.abspath(args.input))}",
                ),
                min_version=original_pdf.pdf_version,
            )
    print("Done.")
    return 0


def create_processor(
    client: DocumentProcessorServiceClient, parent: str, processor_type: str
) -> str:
    """Create a processor for a given processor type."""
    processor = client.create_processor(
        parent=parent,
        processor=Processor(display_name=processor_type, type_=processor_type),
    )
    return processor.name.split("/")[-1]


def find_processor_id_of_type(
    client: DocumentProcessorServiceClient, parent: str, processor_type: str
) -> Optional[str]:
    """Searches for a processor ID for a given processor type."""
    processors = client.list_processors(parent=parent).processors
    for processor in processors:
        if processor.type_ == processor_type:
            # Processor names have the form:
            # `projects/{project}/locations/{location}/processors/{processor_id}`
            # See
            # https://cloud.google.com/document-ai/docs/reference/rpc/google.cloud.documentai.v1beta3#google.cloud.documentai.v1beta3.Processor
            # for more information.
            return processor.name.split("/")[-1]
    return None


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
