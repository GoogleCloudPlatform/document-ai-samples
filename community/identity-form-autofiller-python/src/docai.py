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
import base64
import enum
import io
import re
from collections import defaultdict
from typing import BinaryIO, NamedTuple, Optional

import google.cloud.documentai_v1 as documentai
from PIL import Image
from PIL.Image import Image as PilImage


class ID_PROCESSOR(enum.Enum):
    US_DRIVER_LICENSE_PROCESSOR = "US_DRIVER_LICENSE_PROCESSOR"
    US_PASSPORT_PROCESSOR = "US_PASSPORT_PROCESSOR"
    FR_DRIVER_LICENSE_PROCESSOR = "FR_DRIVER_LICENSE_PROCESSOR"
    FR_NATIONAL_ID_PROCESSOR = "FR_NATIONAL_ID_PROCESSOR"
    ID_FRAUD_DETECTION_PROCESSOR = "ID_FRAUD_DETECTION_PROCESSOR"


class Processor(NamedTuple):
    type: ID_PROCESSOR
    project: str
    location: str
    id: str


class FIELD(enum.Enum):
    # Entity fields
    # See https://cloud.google.com/document-ai/docs/fields#other_processors
    PORTRAIT = "Portrait"
    FAMILY_NAME = "Family Name"
    GIVEN_NAMES = "Given Names"
    DOC_ID = "Document Id"
    EXPIRATION_DATE = "Expiration Date"
    DATE_OF_BIRTH = "Date Of Birth"
    ISSUE_DATE = "Issue Date"
    ADDRESS = "Address"
    MRZ_CODE = "MRZ Code"
    IS_IDENTITY_DOCUMENT = "fraud-signals/is-identity-document"
    SUSPICIOUS_WORDS = "fraud-signals/suspicious-words"
    IMAGE_MANIPULATION = "fraud-signals/image-manipulation"


LOCATIONS = ["us", "eu"]

ID_PROCESSORS = list(map(lambda t: str(t.value), ID_PROCESSOR))

COMMON_FIELDS = [
    FIELD.PORTRAIT,
    FIELD.FAMILY_NAME,
    FIELD.GIVEN_NAMES,
    FIELD.DOC_ID,
    FIELD.EXPIRATION_DATE,
    FIELD.DATE_OF_BIRTH,
    FIELD.ISSUE_DATE,
]

PROCESSOR_FIELDS = {
    ID_PROCESSOR.FR_DRIVER_LICENSE_PROCESSOR: COMMON_FIELDS,
    ID_PROCESSOR.FR_NATIONAL_ID_PROCESSOR: COMMON_FIELDS + [FIELD.ADDRESS],
    ID_PROCESSOR.US_DRIVER_LICENSE_PROCESSOR: COMMON_FIELDS + [FIELD.ADDRESS],
    ID_PROCESSOR.US_PASSPORT_PROCESSOR: COMMON_FIELDS + [FIELD.MRZ_CODE],
    ID_PROCESSOR.ID_FRAUD_DETECTION_PROCESSOR: [
        FIELD.IS_IDENTITY_DOCUMENT,
        FIELD.SUSPICIOUS_WORDS,
        FIELD.IMAGE_MANIPULATION,
    ],
}


def process_document(
    file: BinaryIO,
    mime_type: str,
    project_id: str,
    location: str,
    processor_id: str,
) -> documentai.Document:
    client_options = dict(api_endpoint=f"{location}-documentai.googleapis.com")
    client = documentai.DocumentProcessorServiceClient(client_options=client_options)

    raw_document = documentai.RawDocument(content=file.read(), mime_type=mime_type)
    name = client.processor_path(project_id, location, processor_id)

    request = documentai.ProcessRequest(
        raw_document=raw_document,
        name=name,
        skip_human_review=True,
    )
    response = client.process_document(request)

    return documentai.Document(response.document)


def process_document_with_proc(
    file: BinaryIO, mime_type: str, proc: Processor
) -> documentai.Document:
    return process_document(file, mime_type, proc.project, proc.location, proc.id)


def process_files(files: list[tuple[io.BytesIO, str]], processor: Processor):
    if not files:
        raise ValueError("At least one file is expected")

    if len(files) == 1:
        image_io, mime_type = files[0]
    else:
        images = [Image.open(file) for (file, _) in files]
        image_io, mime_type = group_images_for_processing(images)

    return process_document_with_proc(image_io, mime_type, processor)


def group_images_for_processing(images: list[PilImage]) -> tuple[BinaryIO, str]:
    if len(images) <= 1:
        raise ValueError("At least two image are expected")

    format, mime_type = "tiff", "image/tiff"
    params = dict(save_all=True, append_images=images[1:], compression=None)

    image_io = io.BytesIO()
    images[0].save(image_io, format, **params)
    image_io.seek(0)
    return image_io, mime_type


def processors_locations() -> list[str]:
    return LOCATIONS


def frontend_proc_info(processor_type: str, processor_process_endpoint: str) -> str:
    proc_info = f"{processor_type}|{processor_process_endpoint}"
    return base64.b64encode(proc_info.encode()).decode()


def processor_from_frontend_proc_info(proc_info: str) -> Optional[Processor]:
    proc_info = base64.b64decode(proc_info.encode()).decode()
    PATTERN = (
        r"(?P<type>[A-Z0-9_]+)\|"
        r"https://(?P<endpoint>[a-z0-9-]*documentai.googleapis.com)/v([0-9])+/"
        r"projects/(?P<project>[0-9]+)/"
        r"locations/(?P<location>[a-z0-9-]+)/"
        r"processors/(?P<id>[a-z0-9]+):process"
    )
    if (m := re.match(PATTERN, proc_info)) is None:
        return None

    return Processor(
        ID_PROCESSOR(m.group("type")),
        m.group("project"),
        m.group("location"),
        m.group("id"),
    )


def frontend_id_processors(project_id: str, api_location: str) -> dict[str, str]:
    import docai_procs  # TODO: merge when processor management is updated to v1

    id_processors = dict()

    procs = docai_procs.get_processors_of_types(project_id, api_location, ID_PROCESSORS)
    for proc in procs:
        key = proc.display_name
        value = frontend_proc_info(str(proc.type_), str(proc.process_endpoint))
        id_processors[key] = value

    return id_processors


def check_processors(project_id: str):
    import docai_procs  # TODO: merge when processor management is updated to v1

    docai_procs.check_processors(project_id, LOCATIONS, ID_PROCESSORS)


def get_document(local_sample: str) -> documentai.Document:
    with open(local_sample) as json_file:
        json = json_file.read()
    return documentai.Document(documentai.Document.from_json(json))


def get_processor_fields(processor: Processor) -> dict:
    all = list()
    images = list()

    for field in PROCESSOR_FIELDS[processor.type]:
        all.append(field.value)
        if field == FIELD.PORTRAIT:
            images.append(field.value)

    return dict(all=all, images=images)


def id_data_from_document(document: documentai.Document) -> dict:
    id_data = defaultdict(dict)

    for entity in document.entities:
        key = entity.type_
        page_index = 0
        value = entity.mention_text
        confidence, normalized = None, None

        if entity.page_anchor:
            page_index = entity.page_anchor.page_refs[0].page
        if not value:  # Send the detected portrait image instead
            image = crop_entity(document, entity)
            value = data_url_from_image(image)
        if entity.confidence != 0.0:
            confidence = int(entity.confidence * 100 + 0.5)
        if entity.normalized_value:
            normalized = entity.normalized_value.text

        id_data[key][page_index] = dict(
            value=value,
            confidence=confidence,
            normalized=normalized,
        )

    return id_data


def crop_entity(
    doc: documentai.Document, entity: documentai.Document.Entity
) -> PilImage:
    page_ref = entity.page_anchor.page_refs[0]
    image_page = page_ref.page
    image_content = doc.pages[image_page].image.content

    doc_image = Image.open(io.BytesIO(image_content))
    w, h = doc_image.size
    vertices = vertices_from_bounding_poly(page_ref.bounding_poly, w, h)
    (top, left), (bottom, right) = vertices[0], vertices[2]
    croped_image = doc_image.crop((top, left, bottom, right))

    return croped_image


def vertices_from_bounding_poly(bounding_poly, w, h):
    vertices = bounding_poly.normalized_vertices
    return tuple((v.x * w, v.y * h) for v in vertices)


def data_url_from_image(image: PilImage) -> str:
    image_io = io.BytesIO()
    image.save(image_io, "png")
    base64_string = base64.b64encode(image_io.getvalue()).decode()
    return f"data:image/png;base64,{base64_string}"
