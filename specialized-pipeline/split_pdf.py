# type: ignore[1]
# pylint: skip-file
"""
Split PDF File into SubDocuments based on DocAI Splitter-Classifier Output
"""
from os import path
from io import BytesIO
from typing import Set, Any

from pikepdf import Pdf

from google.cloud.documentai_v1 import Document

from gcs_utils import split_gcs_uri, get_blob_from_gcs, upload_file_to_gcs
from docai_utils import extract_subdocuments

PDF_EXTENSION = ".pdf"


def split_pdf_gcs(
    document: Document, gcs_output_bucket: str, gcs_output_prefix: str
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
    #  If blob not pdf
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


def split_pdf_local(
    document: Document,
    input_pdf_filename: str,
    local_output_dir: str,
    suffix: str = "-pg",
) -> Set[str]:
    """
    Split PDF in local file into separate PDFs based on entity types
    Save Each Subdocument in Folder by Classification
    """
    filename, file_extension = path.splitext(input_pdf_filename)

    if file_extension.lower() != PDF_EXTENSION:
        print(f"Input file {input_pdf_filename} is not a PDF")
        return set()

    subdocument_indexes = extract_subdocuments(document)
    output_directories: Set[str] = set()

    print(f"Creating subdocuments of {input_pdf_filename}")
    with Pdf.open(input_pdf_filename) as original_pdf:
        # Create New PDF for each SubDocument
        for directory, page_nums in subdocument_indexes:
            new_document = Pdf.new()
            new_document_name = f"{local_output_dir}/{directory}/{filename}{suffix}"
            # Add SubDocument Pages to New PDF
            for page_num in page_nums:
                new_document.pages.append(original_pdf.pages[page_num])
                new_document_name = f"{new_document_name}-{page_num}"

            output_directories.add(directory)

            # Save New PDF to File System
            new_document.save(
                f"{new_document_name}{file_extension}",
                min_version=original_pdf.pdf_version,
            )

    return output_directories


def _split_pdf(
    document: Document,
    input_pdf_filename: str,
    output_prefix: str,
    original_pdf: Any,
    suffix: str = "-pg",
) -> Set[str]:

    filename, file_extension = path.splitext(input_pdf_filename)

    if file_extension.lower() != PDF_EXTENSION:
        print(f"Input file {input_pdf_filename} is not a PDF")
        return set()

    output_directories: Set[str] = set()

    print(f"Creating subdocuments of {input_pdf_filename}")

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
                    print(
                        f"Page {page_ref.page} does not exist in {input_pdf_filename}"
                    )
                    continue

            # Split Output Sub-Document File Name
            subdoc_name = (
                f"{output_prefix}/{entity.type_}/{filename}{suffix}{file_extension}"
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

    return output_directories
    return
