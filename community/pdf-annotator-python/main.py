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

"""This module defines a CLI that uses Document AI to annotate a PDF document"""

import argparse
import os
import sys
from typing Optional

import google.auth
import pikepdf
from google.cloud.documentai_v1beta3 import DocumentProcessorServiceClient, Processor

DEFAULT_MULTI_REGION_LOCATION = "us"
DEFAULT_PROCESSOR_TYPE = "FORM_PARSER_PROCESSOR"


def main(args):
    """This functions annotates a PDF document using the Document AI API"""
    if not args.project_id:
        _, project_id = google.auth.default()
        args.project_id = project_id
    parent = f"projects/{args.project_id}/locations/{args.multi_region_location}"
    client = DocumentProcessorServiceClient()

    processor_id = find_processor_id_of_type(client, parent, args.form_processor_type)
    if processor_id is None:
        print(
            f"no form processor found. "
            f'creating new processor of type "{args.form_processor_type}"',
        )
        processor_id = create_processor(client, parent, args.form_processor_type)

    if not os.path.isfile(os.path.abspath(args.input)):
        print(f"could not find file at {os.path.abspath(args.input)}")
        return 1
    # If a output path is not specified, use input directory
    if not args.output:
        args.output = f'{os.path.abspath(args.input).rstrip(".pdf")}_annotated.pdf'

    print("Calling Document AI API...", end="")
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

    original_pdf = pikepdf.Pdf.open(os.path.abspath(args.input))
    annotated_pdf = pikepdf.Pdf.new()
    for page_num, page_info in enumerate(document.pages):
        annotated_pdf.pages.append(original_pdf.pages[page_num])
        print(
            f"Found { len(page_info.form_fields)} form fields on page {page_num + 1}:"
        )
        # Calculate the max "x" and "y" coordinate values for the PDF
        # this uses the PDF's own built in measuring units which need
        # to be used to place annotations
        page_max_x = float(annotated_pdf.pages[page_num].trimbox[2])
        page_max_y = float(annotated_pdf.pages[page_num].trimbox[3])
        page_annotations = []
        for field in page_info.form_fields:
            # Use the normalized vertices of the form fields and the max
            # "x" and "y" coordinates to calculate the position of the
            # annotation using the PDF's built in measuring units
            coord1 = field.field_name.bounding_poly.normalized_vertices[0]
            coord2 = field.field_name.bounding_poly.normalized_vertices[1]
            rect = [
                coord1.x * page_max_x,
                page_max_y - coord1.y * page_max_y,
                coord2.x * page_max_x,
                page_max_y - coord2.y * page_max_y,
            ]
            # Extract the parsed name and values of each field
            # as determined by Document AI's API
            name = layout_to_text(field.field_name, document.text)
            value = layout_to_text(field.field_value, document.text)
            annotation_text = f"{name}: {value}"
            # Create a PDF annotation for this field name value pair
            page_annotations.append(
                pikepdf.Dictionary(
                    Type=pikepdf.Name.Annot,
                    Subtype=pikepdf.Name.Text,
                    Rect=rect,
                    Name=pikepdf.Name.Note,
                    Contents=pikepdf.String(annotation_text),
                    Open=False,
                )
            )
            print(f"adding annotation: {annotation_text}")
        # Add all the annotations for this page
        annotated_pdf.pages[page_num].Annots = annotated_pdf.make_indirect(
            pikepdf.Array(page_annotations)
        )

    print(f"Saving annotated PDF to {args.output}.")
    annotated_pdf.save(
        os.path.join(args.output),
        min_version=original_pdf.pdf_version,
        # Disable annotation modification
        encryption=pikepdf.Encryption(
            owner="", user="", allow=pikepdf.Permissions(modify_annotation=False)
        ),
    )
    print("Done.")
    return 0


def layout_to_text(layout: dict, text: str) -> str:
    """
    Document AI identifies form fields by their offsets in the entirety of the
    document's text. This function converts offsets to a string.
    """
    response = ""
    # If a text segment spans several lines, it will
    # be stored in different text segments.
    for segment in layout.text_anchor.text_segments:  # type: ignore
        start_index = (
            int(segment.start_index)
            if segment in layout.text_anchor.text_segments  # type: ignore
            else 0
        )
        end_index = int(segment.end_index)
        response += text[start_index:end_index]

    # remove whitespace
    response = "".join(response.split("\n"))
    response = "".join(response.split(":"))
    return response.strip()


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
    client: DocumentProcessorServiceClient, parent: str, tartget_processor_type: str
) -> Optional[str]:
    """Searches for a processor ID for a given processor type."""
    for processor in client.list_processors(parent=parent).processors:
        if processor.type_ == tartget_processor_type:
            return processor.name.split("/")[-1]
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Annotate a PDF document.")
    parser.add_argument(
        "-i", "--input", help="filepath of input PDF to annotate", required=True
    )
    parser.add_argument("--output", help="path to save annotated PDF")
    parser.add_argument(
        "--project-id", help="Project ID to use to call the Document AI API"
    )
    parser.add_argument(
        "--multi-region-location",
        help="multi-regional location for document storage and processing",
        default=DEFAULT_MULTI_REGION_LOCATION,
    )
    parser.add_argument(
        "--form-processor-type",
        help='type of form processor e.g. "FORM_W9_PROCESSOR"',
        default=DEFAULT_PROCESSOR_TYPE,
    )
    sys.exit(main(parser.parse_args()))
