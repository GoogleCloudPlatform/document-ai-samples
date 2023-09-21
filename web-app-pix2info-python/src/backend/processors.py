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
import re

from google.cloud.documentai_v1 import DocumentProcessorServiceClient
from google.cloud.documentai_v1 import Processor

# Processing locations (displayed in the frontend)
DEMO_PROCESSING_LOCATIONS = ("us", "eu")

# Processing location used when analyzing a sample
# Samples are json-cached, so this is only useful in dev mode (before deployment)
# Choose according to your development location:
# - A closer location will provide better latencies
# - Different locations will provide identical results (except if regulations differ)
SAMPLE_PROCESSING_LOCATION = "us"
assert SAMPLE_PROCESSING_LOCATION in DEMO_PROCESSING_LOCATIONS

# Document AI processors used in this demo
# See https://cloud.google.com/document-ai/docs/processors-list
DEMO_PROCESSOR_TYPES = (
    "OCR_PROCESSOR",
    "FORM_PARSER_PROCESSOR",
    "EXPENSE_PROCESSOR",
    "INVOICE_PROCESSOR",
    "US_PASSPORT_PROCESSOR",
    "ID_PROOFING_PROCESSOR",
)


def encode_processor_info(processor: Processor) -> str:
    """Return an opaque string to store processor info in the frontend."""
    mapping = DocumentProcessorServiceClient.parse_processor_path(processor.name)
    location = mapping["location"]
    processor_id = mapping["processor"]

    return f"{location}_{processor_id}"


def decode_processor_info(frontend_processor_info: str) -> tuple[str, str]:
    """Return the processor location and ID (input was returned by encode_processor_info())."""
    pattern = r"(?P<location>[a-z0-9-]+)_(?P<processor_id>[a-z0-9]+)"
    m = re.match(pattern, frontend_processor_info)
    if m is None:
        raise ValueError(f"Incorrect processor info: {frontend_processor_info}")
    location = m.group("location")
    processor_id = m.group("processor_id")

    return location, processor_id
