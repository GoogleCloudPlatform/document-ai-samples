"""
Split PDF File into SubDocuments based on DocAI Splitter-Classifier Output
"""
from os import path
from io import BytesIO

from pikepdf import Pdf

from google.cloud import documentai_v1 as documentai

from consts import GCS_SPLIT_PREFIX
from gcs_utils import split_gcs_uri, get_blob_from_gcs, upload_file_to_gcs


def split_pdf_gcs(
    document: documentai.Document,
    gcs_pdf_uri: str,
) -> None:
    """
    Split PDF from GCS into separate PDFs based on entity types
    Save Each Subdocument in GCS Folder by Classification
    """
    # TODO: Remove gcs_pdf_uri and use document.uri when bug is fixed
    bucket_name, object_name = split_gcs_uri(gcs_pdf_uri)

    if ".pdf" not in object_name:
        print(f"Input file {object_name} is not a PDF")
        return

    input_file_blob = get_blob_from_gcs(bucket_name, object_name)

    filename, file_extension = path.splitext(object_name)

    with Pdf.open(BytesIO(input_file_blob.download_as_bytes())) as original_pdf:
        # Extract SubDocuments for each entity
        for index, entity in enumerate(document.entities):

            subdoc = Pdf.new()
            suffix = "-pg"

            for page_ref in entity.page_anchor.page_refs:
                subdoc.pages.append(original_pdf.pages[int(page_ref.page)])
                suffix = f"{suffix}-{page_ref.page}"

            subdoc_uri = (
                f"{GCS_SPLIT_PREFIX}/{entity.type_}/{filename}{suffix}{file_extension}"
            )

            print(
                f"Creating subdocument {index} of {len(document.entities) - 1} - {subdoc_uri}."
            )

            # TODO: Change upload to keep PDF mime type, currently saves as application/octet-stream
            subdoc_bytes = BytesIO()
            subdoc.save(
                subdoc_bytes,
                min_version=original_pdf.pdf_version,
            )
            subdoc_bytes.seek(0)

            # Upload to GCS in directory gs://<bucket>/<classification>/filename-pg123.pdf
            upload_file_to_gcs(subdoc_bytes, bucket_name, subdoc_uri)
