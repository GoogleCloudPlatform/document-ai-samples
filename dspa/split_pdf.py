# type: ignore[1]
# pylint: skip-file
"""
Split PDF File into SubDocuments based on DocAI Splitter-Classifier Output
"""
from os import path
from io import BytesIO
from typing import Set

from pikepdf import Pdf

from google.cloud import documentai_v1 as documentai

from gcs_utils import split_gcs_uri, get_blob_from_gcs, upload_file_to_gcs


def split_pdf_gcs(
    document: documentai.Document, gcs_output_bucket: str, gcs_output_prefix: str
) -> Set[str]:
    """
    Split PDF from GCS into separate PDFs based on entity types
    Save Each Subdocument in GCS Folder by Classification
    """
    # Download original PDF from GCS
    input_bucket_name, object_name = split_gcs_uri(document.uri)

    if ".pdf" not in object_name.lower():
        print(f"Input file {object_name} is not a PDF")
        return set()

    input_file_blob = get_blob_from_gcs(input_bucket_name, object_name)

    filename, file_extension = path.splitext(object_name)

    classifications: Set[str] = set()

    print(f"Creating subdocuments of {object_name}")

    with Pdf.open(BytesIO(input_file_blob.download_as_bytes())) as original_pdf:
        # Extract SubDocuments for each entity
        for entity in document.entities:
            subdoc = Pdf.new()
            suffix = "-pg"

            # Get Page Range for SubDocument
            for page_ref in entity.page_anchor.page_refs:
                try:
                    subdoc.pages.append(original_pdf.pages[int(page_ref.page)])
                    suffix = f"{suffix}-{page_ref.page}"
                except IndexError:
                    print(f"Page {page_ref.page} does not exist in {object_name}")
                    continue

            # Split Output Sub-Document File Name
            subdoc_name = (
                f"{gcs_output_prefix}/{entity.type_}/{filename}{suffix}{file_extension}"
            )
            classifications.add(entity.type_)

            print(f"gs://{gcs_output_bucket}/{subdoc_name}")

            # Save Sub-PDF to Memory
            subdoc_bytes = BytesIO()
            subdoc.save(
                subdoc_bytes,
                min_version=original_pdf.pdf_version,
            )
            subdoc_bytes.seek(0)

            # Upload to GCS in directory gs://<bucket>/<classification>/filename-pg123.pdf
            upload_file_to_gcs(subdoc_bytes, gcs_output_bucket, subdoc_name)

    return classifications
