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

PROCESSOR_NAME_PREFIX = "demo-"
PROCESSOR_CONFIG_FIELD = "docai_active_processors"


def setup():
    """
    Run Initialization Steps
    """
    # List Available Processor Types
    available_processor_types = fetch_processor_types(
        DOCAI_PROJECT_ID, DOCAI_LOCATION)

    # Create Processors
    for processor_type in available_processor_types:
        processor_type_name = processor_type.type_

        if not processor_type.allow_creation:
            print(f"Skipping processor type {processor_type_name}")
            continue

        print(f"Creating Processor: {processor_type_name}")
        display_name = f"{PROCESSOR_NAME_PREFIX}{processor_type_name.lower()}"

        try:
            processor = create_processor(
                DOCAI_PROJECT_ID, DOCAI_LOCATION, display_name, processor_type=processor_type_name)
        except Exception as exception:
            print("Skipping processor:", processor)
            print(exception)
            continue

        processor_id = get_processor_id(processor.name)
        CONFIG[PROCESSOR_CONFIG_FIELD][processor_type_name] = processor_id
        print(f"Created {display_name}: {processor_id}\n")

    write_yaml(CONFIG_FILE_PATH, CONFIG)


if __name__ == "__main__":
    setup()
