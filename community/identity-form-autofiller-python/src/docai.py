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
from base64 import b64decode, b64encode
from collections import defaultdict
from io import BytesIO
from re import match
from typing import BinaryIO, Sequence, TypeAlias, cast

from google.api_core.client_options import ClientOptions
from google.cloud.documentai_v1 import (
    BoundingPoly,
    Document,
    DocumentProcessorServiceClient,
    NormalizedVertex,
    ProcessRequest,
    RawDocument,
)
from PIL import Image
from PIL.Image import Image as PilImage

from docai_schemas import (
    FIELD,
    ID_PROCESSOR,
    ID_PROCESSORS,
    LEGACY_NON_SNAKE_CASE_PROCESSORS,
    LOCATIONS,
    PROCESSOR_FIELD_REPLACEMENTS,
    PROCESSOR_FIELDS,
    Processor,
)

PageAnchor: TypeAlias = Document.PageAnchor
PageRef: TypeAlias = Document.PageAnchor.PageRef
PageRefs: TypeAlias = Sequence[Document.PageAnchor.PageRef]
Entity: TypeAlias = Document.Entity
Entities: TypeAlias = Sequence[Document.Entity]
NormalizedValue: TypeAlias = Document.Entity.NormalizedValue
TextAnchor: TypeAlias = Document.TextAnchor
TextSegment: TypeAlias = Document.TextAnchor.TextSegment
TextSegments: TypeAlias = Sequence[Document.TextAnchor.TextSegment]
Page: TypeAlias = Document.Page
Pages: TypeAlias = Sequence[Document.Page]
PageImage: TypeAlias = Document.Page.Image
NormalizedVertices: TypeAlias = Sequence[NormalizedVertex]


def process_document(
    file: BinaryIO,
    mime_type: str,
    project_id: str,
    location: str,
    processor_id: str,
) -> Document:
    """Analyze the input file with Document AI and return a structured document."""
    client_options = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    client = DocumentProcessorServiceClient(client_options=client_options)

    raw_document = RawDocument(content=file.read(), mime_type=mime_type)
    name = client.processor_path(project_id, location, processor_id)

    request = ProcessRequest(
        raw_document=raw_document,
        name=name,
        skip_human_review=True,
    )
    response = client.process_document(request)

    return cast(Document, response.document)


def process_document_with_proc(
    file: BinaryIO,
    mime_type: str,
    proc: Processor,
) -> Document:
    """Analyze the input file with Document AI and return a structured document."""
    return process_document(file, mime_type, proc.project, proc.location, proc.id)


def process_files(
    files: Sequence[tuple[BytesIO, str]],
    processor: Processor,
) -> Document:
    """Analyze input files with Document AI and return a structured document."""
    if not files:
        raise ValueError("At least one file is expected")

    if len(files) == 1:
        image_io, mime_type = files[0]
    else:
        images = [Image.open(file) for (file, _) in files]
        image_io, mime_type = group_images_in_tiff_container(images)

    return process_document_with_proc(image_io, mime_type, processor)


def group_images_in_tiff_container(images: Sequence[PilImage]) -> tuple[BytesIO, str]:
    """Group input images into single container to be processed by Document AI."""
    if len(images) < 2:
        raise ValueError("At least two images are expected")

    format, mime_type = "tiff", "image/tiff"
    params = dict(save_all=True, append_images=images[1:], compression=None)

    image_io = BytesIO()
    images[0].save(image_io, format, **params)
    image_io.seek(0)

    return image_io, mime_type


def processor_locations() -> Sequence[str]:
    return LOCATIONS


def frontend_proc_info(processor_type: str, processor_process_endpoint: str) -> str:
    """Return processor info (opaque string) for exchanges with frontend."""
    proc_info = f"{processor_type}|{processor_process_endpoint}"

    return b64encode(proc_info.encode()).decode()


def processor_from_frontend_proc_info(proc_info: str) -> Processor | None:
    """Return processor from opaque string (see frontend_proc_info)."""
    proc_info = b64decode(proc_info.encode()).decode()
    PATTERN = (
        r"(?P<type>[A-Z0-9_]+)\|"
        r"https://(?P<endpoint>[a-z0-9-]*documentai.googleapis.com)/v([0-9])+/"
        r"projects/(?P<project>[0-9]+)/"
        r"locations/(?P<location>[a-z0-9-]+)/"
        r"processors/(?P<id>[a-z0-9]+):process"
    )
    if (m := match(PATTERN, proc_info)) is None:
        return None

    return Processor(
        ID_PROCESSOR[m.group("type")],
        m.group("project"),
        m.group("location"),
        m.group("id"),
    )


def frontend_id_processors(project_id: str, api_location: str) -> dict[str, str]:
    """Return mapping of identity processors to be displayed by frontend.
    Keys are processor display names, values are opaque strings.
    """
    import docai_procs  # TODO: merge when processor management is updated to v1

    id_processors = dict()

    client, parent = docai_procs.get_client_and_parent(project_id, api_location)
    procs = docai_procs.get_processors_of_types(client, parent, ID_PROCESSORS)
    for proc in procs:
        key = proc.display_name
        value = frontend_proc_info(str(proc.type_), str(proc.process_endpoint))
        id_processors[key] = value

    return id_processors


def check_create_processors(project_id: str):
    """Check/create demo processors."""
    import docai_procs  # TODO: merge when processor management is updated to v1

    docai_procs.check_create_processors(project_id, LOCATIONS, ID_PROCESSORS)


def get_document(local_sample: str) -> Document:
    """Return document from JSON serialization."""
    with open(local_sample) as json_file:
        json = json_file.read()

    return cast(Document, Document.from_json(json))


def get_processor_fields(processor: Processor) -> dict:
    """Return processor field mapping for frontend."""
    all = list()
    images = list()

    proc_type = processor.type
    replacements = PROCESSOR_FIELD_REPLACEMENTS.get(proc_type, {})
    snake_case = proc_type not in LEGACY_NON_SNAKE_CASE_PROCESSORS

    for field in PROCESSOR_FIELDS[proc_type]:
        field = replacements.get(field, field)
        value = to_snake_case(field.value) if snake_case else field.value
        all.append(value)
        if field == FIELD.PORTRAIT:
            images.append(value)

    return dict(all=all, images=images)


def to_snake_case(field: str) -> str:
    """Return string converted to snake case (e.g. "Given Name" -> "given_name")."""
    return "".join("_" if c == " " else c.lower() for c in field)


def id_data_from_document(document: Document) -> dict:
    """Return ID data mapping for frontend."""
    id_data: dict = defaultdict(dict)

    entities = cast(Entities, document.entities)
    for entity in entities:
        key = cast(str, entity.type_)
        page_index = 0
        confidence, normalized = None, None
        page_anchor = cast(PageAnchor, entity.page_anchor)
        page_refs = cast(PageRefs, page_anchor.page_refs)
        page_index = cast(int, page_refs[0].page) if page_refs else 0

        if key.lower() == FIELD.PORTRAIT.value.lower():
            image = crop_entity(document, entity)
            value = data_url_from_image(image)
        else:
            value = text_from_entity(document, entity)

        confidence = cast(float, entity.confidence)
        if confidence != 0.0:
            confidence = int(confidence * 100 + 0.5)
        if entity.normalized_value:
            normalized_value = cast(NormalizedValue, entity.normalized_value)
            normalized = normalized_value.text

        id_data[key][page_index] = dict(
            value=value,
            confidence=confidence,
            normalized=normalized,
        )

    return id_data


def text_from_entity(doc: Document, entity: Entity) -> str:
    """Return a single string of line-break-separated text segments."""
    text_anchor = cast(TextAnchor, entity.text_anchor)
    text_segments = cast(TextSegments, text_anchor.text_segments)

    if not text_segments:
        # Some processors can return entity text unrelated to the document text
        # e.g. ID_FRAUD_DETECTION_PROCESSOR
        return cast(str, entity.mention_text)

    # For demo purposes, return line breaks so they can be made visible in the UI
    full_text = cast(str, doc.text)
    text = "\n".join(
        full_text[cast(int, ts.start_index) : cast(int, ts.end_index)]
        for ts in text_segments
    )

    return text


def crop_entity(doc: Document, entity: Document.Entity) -> PilImage:
    """Return image cropped from page image for detected entity."""
    page_anchor = cast(PageAnchor, entity.page_anchor)
    page_refs = cast(PageRefs, page_anchor.page_refs)
    page_ref = page_refs[0]
    image_page = cast(int, page_ref.page)
    doc_page = cast(Pages, doc.pages)[image_page]
    page_image = cast(PageImage, doc_page.image)
    image_content = cast(bytes, page_image.content)

    doc_image = Image.open(BytesIO(image_content))
    w, h = doc_image.size
    bounding_poly = cast(BoundingPoly, page_ref.bounding_poly)
    vertices = vertices_from_bounding_poly(bounding_poly, w, h)
    (top, left), (bottom, right) = vertices[0], vertices[2]
    cropped_image = doc_image.crop((top, left, bottom, right))

    return cropped_image


def vertices_from_bounding_poly(
    bounding_poly: BoundingPoly, w: int, h: int
) -> Sequence[tuple[int, int]]:
    """Return bounding polygon vertices as image coordinates."""
    vertices = cast(NormalizedVertices, bounding_poly.normalized_vertices)

    return [
        (
            int(cast(float, v.x) * w + 0.5),
            int(cast(float, v.y) * h + 0.5),
        )
        for v in vertices
    ]


def data_url_from_image(image: PilImage) -> str:
    """Convert image into frontend data URL."""
    image_io = BytesIO()
    image.save(image_io, "png")
    base64_string = b64encode(image_io.getvalue()).decode()

    return f"data:image/png;base64,{base64_string}"
