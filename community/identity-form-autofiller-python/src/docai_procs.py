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
# TODO: merge with docai.py once processor management is released in v1
import google.cloud.documentai_v1beta3 as documentai


def get_client(api_location: str) -> documentai.DocumentProcessorServiceClient:
    client_options = dict(api_endpoint=f"{api_location}-documentai.googleapis.com")

    return documentai.DocumentProcessorServiceClient(client_options=client_options)


def get_client_and_parent(
    project_id: str,
    api_location: str,
) -> tuple[documentai.DocumentProcessorServiceClient, str]:
    client = get_client(api_location)
    parent = client.common_location_path(project_id, api_location)

    return client, parent


def get_processor_types(project_id: str, api_location: str) -> list[str]:
    client, parent = get_client_and_parent(project_id, api_location)
    response = client.fetch_processor_types(parent=parent)

    return list(response.processor_types)


def get_processors_of_types(
    project_id: str,
    api_location: str,
    proc_types: list[str],
) -> list[documentai.Processor]:
    client, parent = get_client_and_parent(project_id, api_location)
    response = client.list_processors(parent=parent)

    processors = [
        proc
        for proc in response.processors
        if proc.type_ in proc_types and proc.state == documentai.Processor.State.ENABLED
    ]

    return processors


def check_processors(project_id, locations: list[str], proc_types: list[str]):
    """Check if expected processors exist and create them otherwise.
    - For demo purposes, processor display names are identical to the processor types.
    - Rights required for the service account: "roles/documentai.editor"
    """
    for location in locations:
        existing_names = [
            str(proc.display_name)
            for proc in get_processors_of_types(project_id, location, proc_types)
        ]
        client, parent = get_client_and_parent(project_id, location)

        for proc_type in proc_types:
            try:
                expected_name = proc_type
                if expected_name in existing_names:
                    print(f"OK existing: {location} / {expected_name}")
                    continue

                print(f".. Creating: {location} / {expected_name}")
                processor = documentai.Processor(
                    display_name=expected_name, type_=proc_type
                )
                client.create_processor(parent=parent, processor=processor)
            except Exception as err:
                error_first_line = str(err).split("\n")[0]
                print(f"## Error: {error_first_line}")
