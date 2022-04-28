"""
Contains a Map between Specialized Processor Types and Specialized Classifier Output
"""


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


# Processors that Split & Classify
CLASSIFIER_PROCESSOR_TYPES = set([
    "PROCUREMENT_DOCUMENT_SPLIT_PROCESSOR",
    "LENDING_DOCUMENT_SPLIT_PROCESSOR"
])

# Map Processor Type to Classifier Output
PROCESSOR_SUPPORTED_DOCUMENT_TYPES = {
    # Default for all non-classified documents
    "FORM_PARSER_PROCESSOR": ["other"],
    # Procurement Processors
    "UTILITY_PROCESSOR": ["utility_statement"],
    "INVOICE_PROCESSOR": [
        "debit_note",
        "credit_note",
        "invoice_statement"
    ],
    "EXPENSE_PROCESSOR": [
        "credit_card_slip",
        "restaurant_statement",
        "air_travel_statement",
        "hotel_statement",
        "car_rental_statement",
        "ground_transportation_statement",
        "receipt_statement"
    ],
    # Lending Processors
    'BANK_STATEMENT_PROCESSOR': ['account_statement_bank'],
    'FORM_1040SCH_C_PROCESSOR': ['1040sc',
                                 '1040sc_2018',
                                 '1040sc_2019',
                                 '1040sc_2020',
                                 '1040sc_2021'],
    'FORM_1040_PROCESSOR': ['1040',
                            '1040_2018',
                            '1040_2019',
                            '1040_2020',
                            '1040_2021'],
    'FORM_1099DIV_PROCESSOR': ['1099div',
                               '1099div_2018',
                               '1099div_2019',
                               '1099div_2020',
                               '1099div_2021'],
    'FORM_1099INT_PROCESSOR': ['1099int',
                               '1099int_2018',
                               '1099int_2019',
                               '1099int_2020',
                               '1099int_2021'],
    'FORM_1099MISC_PROCESSOR': ['1099misc',
                                '1099misc_2018',
                                '1099misc_2019',
                                '1099misc_2020',
                                '1099misc_2021'],
    'FORM_1099NEC_PROCESSOR': ['1099nec',
                               '1099nec_2018',
                               '1099nec_2019',
                               '1099nec_2020',
                               '1099nec_2021'],
    'FORM_1099R_PROCESSOR': ['1099r',
                             '1099r_2018',
                             '1099r_2019',
                             '1099r_2020',
                             '1099r_2021'],
    'FORM_W2_PROCESSOR': ['w2',
                          'w2_2018',
                          'w2_2019',
                          'w2_2020',
                          'w2_2021'],
    'FORM_W9_PROCESSOR': ['w9',
                          'w9_2017',
                          'w9_2018',
                          'w9_2019',
                          'w9_2020',
                          'w9_2021'],
    'MORTGAGE_STATEMENT_PROCESSOR': ['mortgage_statements'],
    'PAYSTUB_PROCESSOR': ['payslip'],
    'RETIREMENT_INVESTMENT_STATEMENT_PROCESSOR': ['account_statement_investment_and_retirement'],

    # Identity Processors (Classified using Lending Classifier)
    'US_DRIVER_LICENSE_PROCESSOR': ['us_driver_license'],
    'US_PASSPORT_PROCESSOR': ['us_passport']
}

DOCUMENT_SUPPORTED_PROCESSOR_TYPES = invert_dictionary_with_array(
    PROCESSOR_SUPPORTED_DOCUMENT_TYPES)
