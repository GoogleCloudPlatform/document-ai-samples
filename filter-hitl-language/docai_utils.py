"""
Document AI Functions
"""
from collections import defaultdict
from typing import Any

from google.cloud import documentai_v1 as documentai

from gcs_utils import (
    get_files_from_gcs,
    get_all_buckets,
    create_bucket,
    move_file,
)

UNDEFINED_LANGUAGE = "und"


def sort_document_files_by_language(
    gcs_input_bucket: str, gcs_input_prefix: str, gcs_output_bucket: str
) -> None:
    """
    Move files between buckets based on language
    """

    blobs = get_files_from_gcs(gcs_input_bucket, gcs_input_prefix)
    buckets = get_all_buckets()

    # Output Document.json Files
    for blob in blobs:
        if ".json" not in blob.name:
            print(f"Skipping non-supported file type {blob.name}")
            continue

        print(f"Downloading {blob.name}")
        document = documentai.types.Document.from_json(
            blob.download_as_bytes(), ignore_unknown_fields=True
        )

        # Find the most frequent language in the document
        predominant_language = get_most_frequent_language(document)
        print(f"Predominant Language: {predominant_language}")

        # Create the output bucket if it does not exist
        language_bucket_name = f"{gcs_output_bucket}{predominant_language}"
        if language_bucket_name not in buckets:
            print(f"Creating bucket {language_bucket_name}")
            create_bucket(language_bucket_name)
            buckets.add(language_bucket_name)

        # Move Document.json file to bucket based on language
        move_file(gcs_input_bucket, blob.name, language_bucket_name)


def get_most_frequent_language(document: documentai.Document) -> str:
    """
    Returns the most frequent language in the document
    """

    language_frequency: defaultdict[Any, int] = defaultdict(int)

    for page in document.pages:
        for language in page.detected_languages:
            if language.language_code == UNDEFINED_LANGUAGE or (
                language.confidence and language.confidence < 0.5
            ):
                continue
            language_frequency[language.language_code] += 1

    # type: ignore
    return max(
        language_frequency, key=language_frequency.get, default=UNDEFINED_LANGUAGE
    )
