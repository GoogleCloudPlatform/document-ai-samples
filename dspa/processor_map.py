"""
Contains a Map between Specialized Processor Types and Specialized Classifier Output
"""
from typing import Dict, List

from consts import INVOICE_PARSER_PROCESSOR, BILL_OF_LADING_PROCESSOR


def invert_dictionary_with_array(dictionary: dict):
    """
    Inverts a dictionary with arrays as values
    e.g. {key: [value1, value2]} -> {value1: key, value2: key}
    """
    inv_map = {}
    for key, array in dictionary.items():
        for value in array:
            inv_map[value] = key
    return inv_map


# Map of Processor ID to Supported Document Classes
PROCESSOR_SUPPORTED_DOCUMENT_TYPES: Dict[str, List] = {
    INVOICE_PARSER_PROCESSOR["processor_id"]: [
        "airway_bill",
        "commercial_invoice",
        "importer_security_filing",
        "invoice_logistics",
        "invoice_statement",
        "other",
        "packing_list",
        "seaway_bill",
        "tax_invoice",
    ],
    BILL_OF_LADING_PROCESSOR["processor_id"]: [
        "bill_of_lading",
        "bill_of_lading_supplement",
    ],
}

# Map of Document Type to Processor ID
DOCUMENT_PROCESSOR_MAP = invert_dictionary_with_array(
    PROCESSOR_SUPPORTED_DOCUMENT_TYPES
)
