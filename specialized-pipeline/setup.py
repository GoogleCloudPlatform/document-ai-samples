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

"""Initialize Document AI Processors and Config File"""

from google.api_core.exceptions import GoogleAPICallError

from consts import (
    CONFIG,
    DEFAULT_PROJECT_ID,
    DEFAULT_LOCATION,
    GCS_REGION,
    GCS_INPUT_BUCKET,
    GCS_OUTPUT_BUCKET,
    GCS_ARCHIVE_BUCKET,
    GCS_SPLIT_BUCKET,
    write_yaml,
)

from docai_processors import create_processor, fetch_processor_types

from gcs_utils import create_bucket

PROCESSOR_NAME_PREFIX = "demo2022-"
PROCESSOR_CONFIG_FIELD = "document_ai"

DEMO_PROCESSORS = set(
    {
        "FORM_PARSER_PROCESSOR",
        "LENDING_DOCUMENT_SPLIT_PROCESSOR",
        "FORM_1099DIV_PROCESSOR",
        "FORM_1099INT_PROCESSOR",
        "FORM_1099MISC_PROCESSOR",
        "FORM_1099NEC_PROCESSOR",
        "FORM_W2_PROCESSOR",
    }
)


def create_docai_processors():
    """
    Create Document AI Processors
    """
    # List Available Processor Types
    available_processor_types = fetch_processor_types(
        DEFAULT_PROJECT_ID, DEFAULT_LOCATION
    )

    created_processors = {}

    # Create Processors
    for processor_type in available_processor_types:
        processor_type_name = processor_type.type_

        if processor_type_name not in DEMO_PROCESSORS:
            # Skip Non-Demo Processors
            continue

        if not processor_type.allow_creation:
            print(
                f"Project {DEFAULT_PROJECT_ID} does not have \
                    permission to create {processor_type_name}."
            )
            continue

        display_name = f"{PROCESSOR_NAME_PREFIX}{processor_type_name.lower()}"
        print(f"Creating Processor: {display_name}")

        try:
            processor = create_processor(
                DEFAULT_PROJECT_ID,
                DEFAULT_LOCATION,
                display_name,
                processor_type=processor_type_name,
            )
        except GoogleAPICallError as exception:
            print("Could not create processor:", display_name)
            print(exception)
            continue

        created_processors[processor_type_name] = processor.name

        print(f"Created {display_name}: {processor.name}\n")

    # Write Processor IDs to Config File
    CONFIG.update({PROCESSOR_CONFIG_FIELD: created_processors})
    write_yaml(CONFIG)


def create_gcs_buckets():
    """
    Create Cloud Storage Buckets (If they don't already exist)
    """
    create_bucket(GCS_INPUT_BUCKET, project_id=DEFAULT_PROJECT_ID, location=GCS_REGION)
    create_bucket(GCS_OUTPUT_BUCKET, project_id=DEFAULT_PROJECT_ID, location=GCS_REGION)
    create_bucket(
        GCS_ARCHIVE_BUCKET, project_id=DEFAULT_PROJECT_ID, location=GCS_REGION
    )
    create_bucket(GCS_SPLIT_BUCKET, project_id=DEFAULT_PROJECT_ID, location=GCS_REGION)


def setup():
    """
    Run Initialization Steps
    """
    create_docai_processors()
    create_gcs_buckets()


if __name__ == "__main__":
    setup()
