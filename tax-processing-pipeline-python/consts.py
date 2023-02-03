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

"""DocAI End-to-End Pipeline Demo Constant Definitions"""

from general_utils import invert_dictionary_with_array
from general_utils import read_yaml

# Processors that Split & Classify
CLASSIFIER_PROCESSOR_TYPES = set(
    [
        "LENDING_DOCUMENT_SPLIT_PROCESSOR",
    ]
)

# Map Processor Type to Classifier Output
PROCESSOR_SUPPORTED_DOCUMENT_TYPES = {
    # Default for all non-classified documents
    "FORM_PARSER_PROCESSOR": ["other"],
    # Lending Processors
    "BANK_STATEMENT_PROCESSOR": ["account_statement_bank"],
    "FORM_1040SCH_C_PROCESSOR": [
        "1040sc",
        "1040sc_2018",
        "1040sc_2019",
        "1040sc_2020",
        "1040sc_2021",
    ],
    "FORM_1040_PROCESSOR": [
        "1040",
        "1040_2018",
        "1040_2019",
        "1040_2020",
        "1040_2021",
    ],
    "FORM_1099DIV_PROCESSOR": [
        "1099div",
        "1099div_2018",
        "1099div_2019",
        "1099div_2020",
        "1099div_2021",
    ],
    "FORM_1099INT_PROCESSOR": [
        "1099int",
        "1099int_2018",
        "1099int_2019",
        "1099int_2020",
        "1099int_2021",
    ],
    "FORM_1099MISC_PROCESSOR": [
        "1099misc",
        "1099misc_2018",
        "1099misc_2019",
        "1099misc_2020",
        "1099misc_2021",
    ],
    "FORM_1099NEC_PROCESSOR": [
        "1099nec",
        "1099nec_2018",
        "1099nec_2019",
        "1099nec_2020",
        "1099nec_2021",
    ],
    "FORM_1099R_PROCESSOR": [
        "1099r",
        "1099r_2018",
        "1099r_2019",
        "1099r_2020",
        "1099r_2021",
    ],
    "FORM_W2_PROCESSOR": ["w2", "w2_2018", "w2_2019", "w2_2020", "w2_2021"],
    "FORM_W9_PROCESSOR": [
        "w9",
        "w9_2017",
        "w9_2018",
        "w9_2019",
        "w9_2020",
        "w9_2021",
    ],
    "MORTGAGE_STATEMENT_PROCESSOR": ["mortgage_statements"],
    "PAYSTUB_PROCESSOR": ["payslip"],
    "RETIREMENT_INVESTMENT_STATEMENT_PROCESSOR": [
        "account_statement_investment_and_retirement"
    ],
}

DOCUMENT_SUPPORTED_PROCESSOR_TYPES = invert_dictionary_with_array(
    PROCESSOR_SUPPORTED_DOCUMENT_TYPES
)

CONFIG_FILE_PATH = "config.yaml"
CONFIG = read_yaml(CONFIG_FILE_PATH)

DOCAI_PROJECT_ID = CONFIG["docai_project_id"]
DOCAI_PROCESSOR_LOCATION = CONFIG["docai_processor_location"]
DOCAI_ACTIVE_PROCESSORS = CONFIG["docai_active_processors"]

FIRESTORE_PROJECT_ID = CONFIG["firestore"]["project_id"]
FIRESTORE_COLLECTION_PREFIX = CONFIG["firestore"]["collection"]

DEFAULT_MIME_TYPE = "application/pdf"
