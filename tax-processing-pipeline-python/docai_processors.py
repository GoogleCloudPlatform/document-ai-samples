"""
Document AI Processor Management Functions
"""
from typing import Sequence

# As of Feb 2022, only the v1beta3 Client Library supports processor management
from google.cloud import documentai_v1beta3


def get_parent(project_id: str, location: str) -> str:
    """
    Returns the parent path.
    """
    return f"projects/{project_id}/locations/{location}"


def get_processor_id(path: str):
    """
    Extract Processor ID (Hexadecimal Number) from full processor path
    """

    client = documentai_v1beta3.DocumentProcessorServiceClient()
    return client.parse_processor_path(path)["processor"]


def fetch_processor_types(
    project_id: str, location: str
) -> Sequence[documentai_v1beta3.ProcessorType]:
    """
    Returns a list of processor types enabled for the given project.
    """
    client = documentai_v1beta3.DocumentProcessorServiceClient()
    response = client.fetch_processor_types(
        parent=get_parent(project_id, location)
    )
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
