"""
Initialize Document AI Processors and Config File
"""

from docai_processors import create_processor, fetch_processor_types, get_processor_id
from general_utils import read_yaml, write_yaml

CONFIG_FILE_PATH = "config.yaml"

CONFIG = read_yaml(CONFIG_FILE_PATH)

DOCAI_PROJECT_ID = CONFIG["docai_project_id"]
DOCAI_LOCATION = CONFIG["docai_processor_location"]

FIRESTORE_PROJECT_ID = CONFIG['firestore']['project_id']
FIRESTORE_COLLECTION = CONFIG['firestore']['collection']

PROCESSOR_NAME_PREFIX = "taxdemo2022-"
PROCESSOR_CONFIG_FIELD = "docai_active_processors"

TAX_DEMO_PROCESSORS = set([
    "FORM_PARSER_PROCESSOR",
    "LENDING_DOCUMENT_SPLIT_PROCESSOR",
    "FORM_1099DIV_PROCESSOR",
    "FORM_1099INT_PROCESSOR",
    "FORM_1099MISC_PROCESSOR",
    "FORM_1099NEC_PROCESSOR",
    "FORM_W2_PROCESSOR"
])

def setup():
    """
    Run Initialization Steps
    """
    # List Available Processor Types
    available_processor_types = fetch_processor_types(
        DOCAI_PROJECT_ID, DOCAI_LOCATION)

    created_processors = {}

    # Create Processors
    for processor_type in available_processor_types:
        processor_type_name = processor_type.type_

        if processor_type_name not in TAX_DEMO_PROCESSORS:
            # Skip Non-Tax Demo Processors
            continue

        if not processor_type.allow_creation:
            # This demo requires Lending Processors.
            print(f"Project {DOCAI_PROJECT_ID} does not have permission to create {processor_type_name}.")
            print("If you have a business use case for these processors, you can fill out and submit the Document AI limited access customer request form.")
            print("https://docs.google.com/forms/d/e/1FAIpQLSc_6s8jsHLZWWE0aSX0bdmk24XDoPiE_oq5enDApLcp1VKJ-Q/viewform?gxids=7826")
            return

        display_name = f"{PROCESSOR_NAME_PREFIX}{processor_type_name.lower()}"
        print(f"Creating Processor: {display_name}")

        try:
            processor = create_processor(
                DOCAI_PROJECT_ID, DOCAI_LOCATION, display_name, processor_type=processor_type_name)
        except Exception as exception:
            print("Could not create processor:", display_name)
            print(exception)
            return

        processor_id = get_processor_id(processor.name)
        created_processors[processor_type_name] = processor_id

        print(f"Created {display_name}: {processor_id}\n")

    # Write Processor IDs to Config File
    CONFIG.update({
            PROCESSOR_CONFIG_FIELD: created_processors
    })
    write_yaml(CONFIG_FILE_PATH, CONFIG)


if __name__ == "__main__":
    setup()
