"""
Copyright 2022 Google LLC

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
from base64 import b64decode
from base64 import b64encode
from collections import defaultdict
from io import BytesIO
import logging
from pathlib import Path
from re import match
from typing import BinaryIO, cast, Iterator, Mapping, Sequence

from docai_schemas import FIELD
from docai_schemas import ID_PROCESSOR
from docai_schemas import ID_PROCESSORS
from docai_schemas import LEGACY_NON_SNAKE_CASE_PROCESSORS
from docai_schemas import LOCATIONS
from docai_schemas import PROCESSOR_FIELD_REPLACEMENTS
from docai_schemas import PROCESSOR_FIELDS
from docai_schemas import ProcessorInfo
from google.cloud.documentai_v1 import BoundingPoly
from google.cloud.documentai_v1 import Document
from google.cloud.documentai_v1 import DocumentProcessorServiceClient
from google.cloud.documentai_v1 import Processor
from google.cloud.documentai_v1 import ProcessRequest
from google.cloud.documentai_v1 import RawDocument
from PIL import Image
from PIL.Image import Image as PilImage


def get_client(location: str) -> DocumentProcessorServiceClient:
    """Return a Document AI client."""
    client_options = {"api_endpoint": f"{location}-documentai.googleapis.com"}

    return DocumentProcessorServiceClient(client_options=client_options)


def get_client_and_parent(
    project_id: str, location: str
) -> tuple[DocumentProcessorServiceClient, str]:
    """Return a Document AI client and parent."""
    client = get_client(location)
    parent = client.common_location_path(project_id, location)

    return client, parent


def process_document(
    file: BinaryIO,
    mime_type: str,
    project_id: str,
    location: str,
    processor_id: str,
) -> Document:
    """Analyze the input file with Document AI and return a structured document."""
    client = get_client(location)
    raw_document = RawDocument(content=file.read(), mime_type=mime_type)
    name = client.processor_path(project_id, location, processor_id)

    request = ProcessRequest(
        raw_document=raw_document,
        name=name,
        skip_human_review=True,
    )
    response = client.process_document(request)

    return response.document


def process_document_with_proc(
    file: BinaryIO,
    mime_type: str,
    proc: ProcessorInfo,
) -> Document:
    """Analyze the input file with Document AI and return a structured document."""
    return process_document(file, mime_type, proc.project, proc.location, proc.id)


def process_files(
    files: Sequence[tuple[BytesIO, str]],
    processor: ProcessorInfo,
) -> Document:
    """Analyze input files with Document AI and return a structured document."""
    if not files:
        raise ValueError("At least one file is expected")

    if len(files) == 1:
        image_io, mime_type = files[0]
    else:
        images = [file for (file, _) in files]
        image_io, mime_type = group_images_in_tiff_container(images)

    return process_document_with_proc(image_io, mime_type, processor)


def group_images_in_tiff_container(images: Sequence[BytesIO]) -> tuple[BytesIO, str]:
    """Group input images into a single container to be processed by Document AI."""
    if len(images) < 2:
        raise ValueError("At least two images are expected")

    next_images = (Image.open(image) for image in images)
    first_image = next(next_images)
    params = dict(save_all=True, append_images=next_images, compression=None)

    image_io = BytesIO()
    image_format, mime_type = "tiff", "image/tiff"
    first_image.save(image_io, image_format, **params)
    image_io.seek(0)

    return image_io, mime_type


def processor_locations() -> Sequence[str]:
    """Return processing locations to be displayed in the frontend."""
    return LOCATIONS


def frontend_proc_info(processor_type: str, processor_process_endpoint: str) -> str:
    """Return processor info (opaque string) for exchanges with frontend."""
    proc_info = f"{processor_type}|{processor_process_endpoint}"

    return b64encode(proc_info.encode()).decode()


def processor_from_frontend_proc_info(proc_info: str) -> ProcessorInfo | None:
    """Return processor from opaque string (see frontend_proc_info)."""
    proc_info = b64decode(proc_info.encode()).decode()
    PATTERN = (
        r"(?P<type>[A-Z0-9_]+)\|"
        r"https://(?P<endpoint>[a-z0-9-]*documentai\.googleapis.com)/v([0-9])+/"
        r"projects/(?P<project>[0-9]+)/"
        r"locations/(?P<location>[a-z0-9-]+)/"
        r"processors/(?P<id>[a-z0-9]+):process"
    )
    if (m := match(PATTERN, proc_info)) is None:
        return None

    return ProcessorInfo(
        ID_PROCESSOR[m.group("type")],
        m.group("project"),
        m.group("location"),
        m.group("id"),
    )


def frontend_id_processors(project_id: str, api_location: str) -> Mapping[str, str]:
    """Return mapping of identity processors to be displayed by frontend.
    Keys are processor display names, values are opaque strings.
    """
    id_processors: dict[str, str] = {}

    client, parent = get_client_and_parent(project_id, api_location)
    procs = get_processors_of_types(client, parent, ID_PROCESSORS)
    for proc in procs:
        key = proc.display_name
        value = frontend_proc_info(proc.type_, proc.process_endpoint)
        id_processors[key] = value

    return id_processors


def get_document(local_sample: str) -> Document:
    """Return document from JSON serialization."""
    json = Path(local_sample).read_text(encoding="utf-8")

    return cast(Document, Document.from_json(json))


def get_processor_fields(processor: ProcessorInfo) -> Mapping[str, Sequence]:
    """Return processor field mapping for frontend."""
    all_fields = []
    image_fields = []

    proc_type = processor.type
    replacements = PROCESSOR_FIELD_REPLACEMENTS.get(proc_type, {})
    snake_case = proc_type not in LEGACY_NON_SNAKE_CASE_PROCESSORS

    for field in PROCESSOR_FIELDS.get(proc_type, []):
        field = replacements.get(field, field)
        value = to_snake_case(field.value) if snake_case else field.value
        all_fields.append(value)
        if field == FIELD.PORTRAIT:
            image_fields.append(value)

    return dict(all_fields=all_fields, image_fields=image_fields)


def to_snake_case(field: str) -> str:
    """Return string converted to snake case (e.g. "Given Name" -> "given_name")."""
    return "".join("_" if c == " " else c.lower() for c in field)


def id_data_from_document(document: Document) -> Mapping[str, Mapping[int, Mapping]]:
    """Return ID data mapping for frontend."""
    id_data: dict = defaultdict(dict)

    for entity in document.entities:
        key = entity.type_
        page_refs = entity.page_anchor.page_refs
        page_index = page_refs[0].page if page_refs else 0
        confidence = entity.confidence
        normalized = None

        if key.lower() == FIELD.PORTRAIT.value.lower():
            image = crop_entity(document, entity)
            value = data_url_from_image(image)
        else:
            value = text_from_entity(document, entity)

        if confidence != 0.0:
            confidence = int(confidence * 100 + 0.5)
        if entity.normalized_value:
            normalized = entity.normalized_value.text

        id_data[key][page_index] = dict(
            value=value,
            confidence=confidence,
            normalized=normalized,
        )

    return id_data


def text_from_entity(doc: Document, entity: Document.Entity) -> str:
    """Return a single string of line-break-separated text segments."""
    text_segments = entity.text_anchor.text_segments

    if not text_segments:
        # Some processors can return entity text not present in the document text
        # Example: ID_PROOFING_PROCESSOR
        return entity.mention_text

    # For demo purposes, return line breaks so they can be made visible in the UI
    text = "\n".join(doc.text[ts.start_index : ts.end_index] for ts in text_segments)

    return text


def crop_entity(doc: Document, entity: Document.Entity) -> PilImage:
    """Return image cropped from page image for detected entity."""
    page_ref = entity.page_anchor.page_refs[0]
    doc_page = doc.pages[page_ref.page]
    image_content = doc_page.image.content

    doc_image = Image.open(BytesIO(image_content))
    w, h = doc_image.size
    vertices = vertices_from_bounding_poly(page_ref.bounding_poly, w, h)
    (top, left), (bottom, right) = vertices[0], vertices[2]
    cropped_image = doc_image.crop((top, left, bottom, right))

    return cropped_image


def vertices_from_bounding_poly(
    bounding_poly: BoundingPoly, w: int, h: int
) -> Sequence[tuple[int, int]]:
    """Return bounding polygon vertices as image coordinates."""
    vertices = bounding_poly.normalized_vertices

    return [(int(v.x * w + 0.5), int(v.y * h + 0.5)) for v in vertices]


def data_url_from_image(image: PilImage) -> str:
    """Convert image into frontend data URL."""
    image_io = BytesIO()
    image.save(image_io, "png")
    base64_string = b64encode(image_io.getvalue()).decode()

    return f"data:image/png;base64,{base64_string}"


def check_create_processors(project_id: str):
    """Check if expected processors exist and create them otherwise.
    - For demo purposes, processor display names are identical to the processor types.
    - Rights required for the service account: "roles/documentai.editor"
    """
    locations = LOCATIONS
    proc_types = ID_PROCESSORS
    for location in locations:
        client, parent = get_client_and_parent(project_id, location)
        existing_names = [
            proc.display_name
            for proc in get_processors_of_types(client, parent, proc_types)
        ]

        for proc_type in proc_types:
            if proc_type in existing_names:
                logging.info("OK existing: %s / %s", location, proc_type)
                continue
            try:
                logging.info(".. Creating: %s / %s", location, proc_type)
                processor = Processor(display_name=proc_type, type_=proc_type)
                client.create_processor(parent=parent, processor=processor)
            except Exception as e:
                logging.exception(e)


def get_processors_of_types(
    client: DocumentProcessorServiceClient,
    parent: str,
    proc_types: Sequence[str],
) -> Iterator[Processor]:
    """Yield enabled processors belonging to the parent."""
    procs = client.list_processors(parent=parent)
    yield from (
        proc
        for proc in procs
        if proc.type_ in proc_types and proc.state == Processor.State.ENABLED
    )
