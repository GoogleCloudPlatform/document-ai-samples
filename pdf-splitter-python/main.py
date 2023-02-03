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
from typing import Sequence

from google.api_core.client_options import ClientOptions
import google.auth
from google.cloud.documentai import Document
from google.cloud.documentai import DocumentProcessorServiceClient
from google.cloud.documentai import Processor
from google.cloud.documentai import ProcessRequest
from google.cloud.documentai import RawDocument
from pikepdf import Pdf

DEFAULT_MULTI_REGION_LOCATION = "us"
DEFAULT_PROCESSOR_TYPE = "LENDING_DOCUMENT_SPLIT_PROCESSOR"

PDF_MIME_TYPE = "application/pdf"
PDF_EXTENSION = ".pdf"


def main(args: argparse.Namespace) -> int:
    """This project splits a PDF document using the Document AI API to identify split points"""
    if not args.project_id:
        _, project_id = google.auth.default()
        args.project_id = project_id

    file_path = os.path.abspath(args.input)

    if not os.path.isfile(file_path):
        print(f"Could not find file at {file_path}")
        return 1

    if PDF_EXTENSION not in args.input:
        print(f"Input file {args.input} is not a PDF")
        return 1

    if not args.output_dir:
        args.output_dir = os.path.dirname(file_path)

    client = DocumentProcessorServiceClient(
        client_options=ClientOptions(
            api_endpoint=f"{args.multi_region_location}-documentai.googleapis.com"
        )
    )

    processor_name = get_or_create_processor(
        client, args.project_id, args.multi_region_location, args.split_processor_type
    )

    print(
        "Using:\n"
        f'* Project ID: "{args.project_id}"\n'
        f'* Location: "{args.multi_region_location}"\n'
        f'* Processor Name "{processor_name}"\n'
        f'* Input PDF "{os.path.basename(file_path)}"\n'
        f'* Output directory: "{args.output_dir}"\n'
    )

    document = online_process(client, processor_name, file_path)

    document_json = write_document_json(document, file_path, output_dir=args.output_dir)
    print(f"Document AI Output: {document_json}")

    split_pdf(document.entities, file_path, output_dir=args.output_dir)

    print("Done.")
    return 0


def get_or_create_processor(
    client: DocumentProcessorServiceClient,
    project_id: str,
    location: str,
    processor_type: str,
) -> str:
    """
    Searches for a processor name for a given processor type.
    Creates processor if one doesn't exist
    """
    parent = client.common_location_path(project_id, location)

    for processor in client.list_processors(parent=parent):
        if processor.type_ == processor_type:
            # Processor names have the form:
            # `projects/{project}/locations/{location}/processors/{processor_id}`
            # See https://cloud.google.com/document-ai/docs/create-processor for more information.
            return processor.name

    print(
        f"No split processor found. "
        f'creating new processor of type "{processor_type}"',
    )
    processor = client.create_processor(
        parent=parent,
        processor=Processor(display_name=processor_type, type_=processor_type),
    )
    return processor.name


def online_process(
    client: DocumentProcessorServiceClient,
    processor_name: str,
    file_path: str,
    mime_type: str = PDF_MIME_TYPE,
) -> Document:
    """
    Call the specified processors process document API with the contents of
    # the input PDF file as input.
    """
    with open(file_path, "rb") as pdf_file:
        result = client.process_document(
            request=ProcessRequest(
                name=processor_name,
                raw_document=RawDocument(content=pdf_file.read(), mime_type=mime_type),
            )
        )
    return result.document


def write_document_json(document: Document, file_path: str, output_dir: str) -> str:
    """
    Write Document object as JSON file
    """

    # File Path: output_dir/file_name.json
    output_filepath = os.path.join(
        output_dir, f"{os.path.splitext(os.path.basename(file_path))[0]}.json"
    )

    with open(output_filepath, "w", encoding="utf-8") as json_file:
        json_file.write(
            Document.to_json(document, including_default_value_fields=False)
        )

    return output_filepath


def split_pdf(entities: Sequence[Document.Entity], file_path: str, output_dir: str):
    """
    Create subdocuments based on Splitter/Classifier output
    """
    with Pdf.open(file_path) as original_pdf:
        # Create New PDF for each SubDocument
        print(f"Total subdocuments: {len(entities)}")

        for index, entity in enumerate(entities):
            start = int(entity.page_anchor.page_refs[0].page)
            end = int(entity.page_anchor.page_refs[-1].page)
            subdoc_type = entity.type_ or "subdoc"

            if start == end:
                page_range = f"pg{start + 1}"
            else:
                page_range = f"pg{start + 1}-{end + 1}"

            output_filename = f"{page_range}_{subdoc_type}"

            print(f"Creating subdocument {index + 1}: {output_filename}")

            subdoc = Pdf.new()
            for page_num in range(start, end + 1):
                subdoc.pages.append(original_pdf.pages[page_num])

            subdoc.save(
                os.path.join(
                    output_dir,
                    f"{output_filename}_{os.path.basename(file_path)}",
                ),
                min_version=original_pdf.pdf_version,
            )


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
