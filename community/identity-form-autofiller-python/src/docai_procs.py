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
import logging
from typing import Sequence, TypeAlias, cast

from google.api_core.client_options import ClientOptions

# TODO: merge with docai.py once processor management is released in v1
from google.cloud.documentai_v1beta3 import (
    DocumentProcessorServiceClient,
    Processor,
    ProcessorType,
)

Locations: TypeAlias = Sequence[str]
ProcessorTypes: TypeAlias = Sequence[str]
Processors: TypeAlias = Sequence[Processor]


def get_client(location: str) -> DocumentProcessorServiceClient:
    client_options = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")

    return DocumentProcessorServiceClient(client_options=client_options)


def get_client_and_parent(
    project_id: str, location: str
) -> tuple[DocumentProcessorServiceClient, str]:
    client = get_client(location)
    parent = client.common_location_path(project_id, location)

    return client, parent


def get_processor_types(project_id: str, location: str) -> ProcessorTypes:
    client, parent = get_client_and_parent(project_id, location)
    response = client.fetch_processor_types(parent=parent)

    processor_types = [
        cast(str, proc_type.type_)
        for proc_type in cast(Sequence[ProcessorType], response.processor_types)
    ]

    return processor_types


def get_processors_of_types(
    client: DocumentProcessorServiceClient,
    parent: str,
    proc_types: ProcessorTypes,
) -> Processors:
    response = client.list_processors(parent=parent)
    processors = [
        proc
        for proc in response
        if all(
            [
                cast(str, proc.type_) in proc_types,
                cast(Processor.State, proc.state) == Processor.State.ENABLED,
            ]
        )
    ]

    return processors


def check_create_processors(
    project_id: str,
    locations: Locations,
    proc_types: ProcessorTypes,
) -> None:
    """Check if expected processors exist and create them otherwise.
    - For demo purposes, processor display names are identical to the processor types.
    - Rights required for the service account: "roles/documentai.editor"
    """
    for location in locations:
        client, parent = get_client_and_parent(project_id, location)
        existing_names = [
            cast(str, proc.display_name)
            for proc in get_processors_of_types(client, parent, proc_types)
        ]

        for proc_type in proc_types:
            if proc_type in existing_names:
                logging.info(f"OK existing: {location} / {proc_type}")
                continue
            try:
                logging.info(f".. Creating: {location} / {proc_type}")
                processor = Processor(display_name=proc_type, type_=proc_type)
                client.create_processor(parent=parent, processor=processor)
            except Exception as err:
                logging.error(err)
