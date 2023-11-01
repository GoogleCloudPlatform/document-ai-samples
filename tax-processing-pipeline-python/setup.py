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
from typing import Dict

from consts import CONFIG
from consts import CONFIG_FILE_PATH
from consts import DOCAI_PROCESSOR_LOCATION
from consts import DOCAI_PROJECT_ID
from docai_utils import create_processor
from docai_utils import fetch_processor_types
from docai_utils import get_processor_id
from docai_utils import list_processors
from general_utils import write_yaml
from google.api_core.exceptions import GoogleAPICallError

PROCESSOR_NAME_PREFIX = "taxdemo2022-"
PROCESSOR_CONFIG_FIELD = "docai_active_processors"

TAX_DEMO_PROCESSORS = set(
    [
        "FORM_PARSER_PROCESSOR",
        "LENDING_DOCUMENT_SPLIT_PROCESSOR",
        "FORM_1099DIV_PROCESSOR",
        "FORM_1099INT_PROCESSOR",
        "FORM_1099MISC_PROCESSOR",
        "FORM_1099NEC_PROCESSOR",
        "FORM_W2_PROCESSOR",
    ]
)

# pylint: disable-next=line-too-long
ACCESS_REQUEST_URL = "https://docs.google.com/forms/d/e/1FAIpQLSc_6s8jsHLZWWE0aSX0bdmk24XDoPiE_oq5enDApLcp1VKJ-Q/viewform?gxids=7826"  # noqa: E501


def write_to_config(created_processors):
    # Write Processor IDs to Config File
    CONFIG.update({PROCESSOR_CONFIG_FIELD: created_processors})
    write_yaml(CONFIG_FILE_PATH, CONFIG)


def setup():
    """
    Run Initialization Steps
    """
    created_processors: Dict[str, str] = {}

    # Check if processors exist
    created_processors = {
        processor.type_: get_processor_id(processor.name)
        for processor in list_processors(DOCAI_PROJECT_ID, DOCAI_PROCESSOR_LOCATION)
        if PROCESSOR_NAME_PREFIX in processor.display_name
    }

    if created_processors:
        write_to_config(created_processors)
        return

    # List Available Processor Types
    available_processor_types = fetch_processor_types(
        DOCAI_PROJECT_ID, DOCAI_PROCESSOR_LOCATION
    )

    # Create Processors
    for processor_type in available_processor_types:
        processor_type_name = processor_type.type_

        if processor_type_name not in TAX_DEMO_PROCESSORS:
            # Skip Non-Tax Demo Processors
            continue

        if not processor_type.allow_creation:
            # This demo requires Lending Processors.
            print(
                f"Project {DOCAI_PROJECT_ID} does not have \
                    permission to create {processor_type_name}."
            )
            print(
                "If you have a business use case for these processors, you can \
                    fill out and submit the Document AI limited access \
                    customer request form."
            )
            print(ACCESS_REQUEST_URL)
            return

        display_name = f"{PROCESSOR_NAME_PREFIX}{processor_type_name.lower()}"
        print(f"Creating Processor: {display_name}")

        try:
            processor = create_processor(
                DOCAI_PROJECT_ID,
                DOCAI_PROCESSOR_LOCATION,
                display_name,
                processor_type=processor_type_name,
            )
        except GoogleAPICallError as exception:
            print("Could not create processor:", display_name)
            print(exception)
            return

        processor_id = get_processor_id(processor.name)
        created_processors[processor_type_name] = processor_id

        print(f"Created {display_name}: {processor_id}\n")

    write_to_config(created_processors)


if __name__ == "__main__":
    setup()
