# Copyright 2022 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Document AI Processor Management Functions"""

from typing import Sequence

# As of May 2022, only the v1beta3 Client Library supports processor management
from google.cloud import documentai_v1beta3


def get_parent(project_id: str, location: str) -> str:
    """
    Returns the parent path.
    """
    return f"projects/{project_id}/locations/{location}"


def fetch_processor_types(
    project_id: str, location: str
) -> Sequence[documentai_v1beta3.ProcessorType]:
    """
    Returns a list of processor types enabled for the given project.
    """
    client = documentai_v1beta3.DocumentProcessorServiceClient()
    response = client.fetch_processor_types(parent=get_parent(project_id, location))
    return response.processor_types


def create_processor(
    project_id: str, location: str, display_name: str, processor_type: str
) -> documentai_v1beta3.Processor:
    """
    Creates a new processor.
    """
    client = documentai_v1beta3.DocumentProcessorServiceClient()
    processor_info = documentai_v1beta3.Processor(
        display_name=display_name, type_=processor_type
    )
    return client.create_processor(
        parent=get_parent(project_id, location), processor=processor_info
    )
