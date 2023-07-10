"""
Copyright 2023 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from io import BytesIO
import logging
from mimetypes import guess_type
from pathlib import Path
from typing import Any, BinaryIO, cast, Mapping, Sequence, TypeAlias

from google.cloud.documentai_v1 import Document
from google.cloud.documentai_v1 import DocumentProcessorServiceClient
from google.cloud.documentai_v1 import Processor
from google.cloud.documentai_v1 import ProcessRequest
from google.cloud.documentai_v1 import RawDocument
from google.protobuf.json_format import MessageToJson  # type: ignore

from .processors import decode_processor_info
from .processors import DEMO_PROCESSING_LOCATIONS
from .processors import DEMO_PROCESSOR_TYPES
from .processors import encode_processor_info
from .processors import SAMPLE_PROCESSING_LOCATION
from .render import tiff_container_for_images
from .render import will_render_entity

DocumentStream: TypeAlias = BytesIO
MimeType: TypeAlias = str
DocumentIO: TypeAlias = tuple[DocumentStream, MimeType]
DocumentJson: TypeAlias = str
DocumentData: TypeAlias = tuple[Document, DocumentJson]


def get_client(location: str) -> DocumentProcessorServiceClient:
    """Return a Document AI client."""
    client_options = dict(api_endpoint=f"{location}-documentai.googleapis.com")
    return DocumentProcessorServiceClient(client_options=client_options)


def process_document(
    file: BinaryIO,
    mime_type: str,
    project: str,
    location: str,
    processor_id: str,
) -> Document:
    """Analyze the input file with Document AI."""
    client = get_client(location)
    raw_document = RawDocument(content=file.read(), mime_type=mime_type)
    name = client.processor_path(project, location, processor_id)

    request = ProcessRequest(
        raw_document=raw_document,
        name=name,
        skip_human_review=True,
    )
    response = client.process_document(request)

    return response.document


def process_documents(
    documents: Sequence[DocumentIO],
    project: str,
    location: str,
    processor_id: str,
) -> DocumentData:
    """Analyze the input file(s) with Document AI.

    Return both the Document AI object and its json serialization (which can be viewed/cached).
    """
    if not documents:
        raise ValueError("At least one document is expected")

    if len(documents) == 1:
        image_io, mime_type = documents[0]
    else:
        images = [file for (file, _) in documents]
        image_io, mime_type = tiff_container_for_images(images)

    document = process_document(image_io, mime_type, project, location, processor_id)
    json = MessageToJson(
        Document.pb(document),
        preserving_proto_field_name=True,  # Same as Python (switch if camel case is preferred)
        ensure_ascii=False,  # Don't escape characters (easier to read + smaller files)
    )

    return document, json


def process_sample(
    sample_name: str,
    samples_root: Path,
    samples_paths: Sequence[str],
    project: str,
    processor_name: str,
) -> DocumentData:
    """Analyze the sample file(s) with Document AI.

    Analyses are cached. This allows deploying a demo with cached samples only.
    """
    json_path = samples_root.joinpath(processor_name, f"{sample_name}.json")
    if json_path.exists():
        # Use cached json serialization
        json = json_path.read_text(encoding="utf-8")
        document = cast(Document, Document.from_json(json))
        return document, json

    location, processor_id = processor_for_sample(project, processor_name)
    documents: list[DocumentIO] = []
    for samples_file in samples_paths:
        path = samples_root.joinpath(processor_name, samples_file)
        mime_type, _ = guess_type(path)
        if mime_type is None:
            raise RuntimeError(f"Could not determine MIME type for {path}")
        documents.append((BytesIO(path.read_bytes()), mime_type))

    document, json = process_documents(documents, project, location, processor_id)

    # Cache json serialization
    json_path.write_text(json, encoding="utf-8")

    return document, json


def summary_counts_for_document(document: Document) -> Mapping[str, Any]:
    """Return a document summary (for direct use by the frontend)."""

    def total_entities(
        entity: Document.Entity,
        page_ref: Document.PageAnchor.PageRef | None = None,
    ) -> int:
        will_render, page_ref = will_render_entity(entity, page_ref)
        total = 1 if will_render else 0
        total += sum(total_entities(entity, page_ref) for entity in entity.properties)
        return total

    def count_list(int_list: list[int]) -> list:
        return [sum(int_list)] + int_list

    # OCR info in document.pages
    pages = 0
    language_codes: set[str] = set()
    block_counts = []
    paragraph_counts = []
    line_counts = []
    token_counts = []
    field_counts = []
    table_counts = []
    barcode_counts = []
    for page in document.pages:
        pages += 1
        language_codes.update(dl.language_code for dl in page.detected_languages)
        block_counts.append(len(page.blocks))
        paragraph_counts.append(len(page.paragraphs))
        line_counts.append(len(page.lines))
        token_counts.append(len(page.tokens))
        field_counts.append(len(page.form_fields))
        table_counts.append(len(page.tables))
        barcode_counts.append(len(page.detected_barcodes))

    # For entities, page info is at the entity level
    entity_counts = [0] * pages
    for entity in document.entities:
        for page_ref in entity.page_anchor.page_refs:
            page_index = page_ref.page
            entity_counts[page_index] += total_entities(entity)

    return dict(
        pages=pages,
        languages=len(language_codes),
        blocks=count_list(block_counts),
        paragraphs=count_list(paragraph_counts),
        lines=count_list(line_counts),
        tokens=count_list(token_counts),
        fields=count_list(field_counts),
        tables=count_list(table_counts),
        entities=count_list(entity_counts),
        barcodes=count_list(barcode_counts),
    )


def get_client_and_parent(
    project: str, location: str
) -> tuple[DocumentProcessorServiceClient, str]:
    """Return a Document AI client and parent."""
    client = get_client(location)
    parent = client.common_location_path(project, location)

    return client, parent


def frontend_demo_processors(project: str, location: str) -> Mapping[str, str]:
    """Return a mapping of the demo processors to be displayed by the frontend.

    Keys are the processor display names, values are processor-identiying opaque strings.
    """
    demo_processors = {}

    client, parent = get_client_and_parent(project, location)
    procs = get_processors_of_types(client, parent, DEMO_PROCESSOR_TYPES)
    for proc in procs:
        key = proc.display_name
        value = encode_processor_info(proc)
        demo_processors[key] = value

    return demo_processors


def processor_for_sample(project: str, processor_name: str) -> tuple[str, str]:
    """Return the processor location and ID to use for sample analysis."""
    processors = frontend_demo_processors(project, SAMPLE_PROCESSING_LOCATION)
    processor_info = processors[processor_name]

    return decode_processor_info(processor_info)


def processor_display_name(proc_number: int, proc_type: str) -> str:
    """Return an arbitrary name with the following constraints:
    - Will be displayed in the frontend
    - Is also a parent folder for the related sample documents
    - Names will be sorted
    """
    return f"{proc_number}-{proc_type}"  # Example: "1-OCR_PROCESSOR"


def get_processors_of_types(
    client: DocumentProcessorServiceClient,
    parent: str,
    proc_types: Sequence[str],
) -> Sequence[Processor]:
    """Return all enabled processors belonging to the parent."""
    return [
        proc
        for proc in client.list_processors(parent=parent)
        if proc.type_ in proc_types and proc.state == Processor.State.ENABLED
    ]


def setup_processors(project_id: str):
    """Check if expected processors exist and create them otherwise.
    - Display names are arbitrary (index-prefixed here for demo purposes)
    - Rights required for the service account: "roles/documentai.editor"
    """
    locations = DEMO_PROCESSING_LOCATIONS
    proc_types = DEMO_PROCESSOR_TYPES

    for location in locations:
        client, parent = get_client_and_parent(project_id, location)
        existing_names = [
            proc.display_name
            for proc in get_processors_of_types(client, parent, proc_types)
        ]

        for proc_number, proc_type in enumerate(proc_types, start=1):
            display_name = processor_display_name(proc_number, proc_type)
            if display_name in existing_names:
                logging.info("OK existing: %s / %s", location, display_name)
                continue
            try:
                logging.info(".. Creating: %s / %s", location, display_name)
                processor = Processor(display_name=display_name, type_=proc_type)
                client.create_processor(parent=parent, processor=processor)
            except Exception as err:
                logging.exception(err)
