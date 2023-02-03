"""
Copyright 2022 Google LLC

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
from enum import auto
from enum import Enum
from typing import NamedTuple


class ID_PROCESSOR(Enum):
    """Document AI Identity Processors

    See https://cloud.google.com/document-ai/docs/processors-list#specialized_processors
    """

    # General Availability
    US_DRIVER_LICENSE_PROCESSOR = auto()
    US_PASSPORT_PROCESSOR = auto()
    # Public Preview
    ID_PROOFING_PROCESSOR = auto()
    # Limited Preview
    FR_DRIVER_LICENSE_PROCESSOR = auto()
    FR_NATIONAL_ID_PROCESSOR = auto()
    FR_PASSPORT_PROCESSOR = auto()
    # Early Access
    AU_DRIVER_LICENSE_PROCESSOR = auto()
    DE_DRIVER_LICENSE_PROCESSOR = auto()
    DE_PASSPORT_PROCESSOR = auto()
    IN_DRIVER_LICENSE_PROCESSOR = auto()
    IN_PASSPORT_PROCESSOR = auto()
    IN_TAX_CARD_PROCESSOR = auto()
    IN_VOTER_ID_PROCESSOR = auto()
    IN_AADHAR_CARD_PROCESSOR = auto()


class FIELD(Enum):
    """Entity fields

    See https://cloud.google.com/document-ai/docs/fields#specialized_processors
    """

    # Fields potentially shared by multiple processors
    PORTRAIT = "Portrait"
    FAMILY_NAME = "Family Name"
    GIVEN_NAME = "Given Name"
    GIVEN_NAMES = "Given Names"
    DOC_ID = "Document Id"
    EXPIRATION_DATE = "Expiration Date"
    DATE_OF_BIRTH = "Date Of Birth"
    PLACE_OF_BIRTH = "Place Of Birth"
    ISSUE_DATE = "Issue Date"
    ADDRESS = "Address"
    MRZ_CODE = "MRZ Code"
    FULL_NAME = "full_name"
    FATHER_NAME = "father_name"
    ADMINISTRATIVE_AREA = "administrative_area"
    ISSUE_AUTHORITY = "issue_authority"
    SEX = "sex"
    PLACE_OF_ISSUE = "place_of_issue"
    HUSBAND_NAME = "husband_name"
    # Fields specific to the ID_PROOFING_PROCESSOR
    IS_IDENTITY_DOCUMENT = "fraud_signals_is_identity_document"
    SUSPICIOUS_WORDS = "fraud_signals_suspicious_words"
    EVIDENCE_SUSPICIOUS_WORDS = "evidence_suspicious_word"
    EVIDENCE_INCONCLUSIVE_SUSPICIOUS_WORDS = "evidence_inconclusive_suspicious_word"
    IMAGE_MANIPULATION = "fraud_signals_image_manipulation"
    ONLINE_DUPLICATE = "fraud_signals_online_duplicate"
    EVIDENCE_HOSTNAME = "evidence_hostname"
    EVIDENCE_THUMBNAIL_URL = "evidence_thumbnail_url"


class ProcessorInfo(NamedTuple):
    type: ID_PROCESSOR
    project: str
    location: str
    id: str


LOCATIONS = ("us", "eu")

ID_PROCESSORS = tuple(p.name for p in ID_PROCESSOR)

COMMON_FIELDS = (
    FIELD.PORTRAIT,
    FIELD.FAMILY_NAME,
    FIELD.GIVEN_NAMES,
    FIELD.DOC_ID,
    FIELD.EXPIRATION_DATE,
    FIELD.DATE_OF_BIRTH,
    FIELD.ISSUE_DATE,
)

PROCESSOR_FIELDS = {
    ID_PROCESSOR.US_DRIVER_LICENSE_PROCESSOR: (*COMMON_FIELDS, FIELD.ADDRESS),
    ID_PROCESSOR.US_PASSPORT_PROCESSOR: (*COMMON_FIELDS, FIELD.MRZ_CODE),
    ID_PROCESSOR.ID_PROOFING_PROCESSOR: (
        FIELD.IS_IDENTITY_DOCUMENT,
        FIELD.SUSPICIOUS_WORDS,
        FIELD.EVIDENCE_SUSPICIOUS_WORDS,
        FIELD.EVIDENCE_INCONCLUSIVE_SUSPICIOUS_WORDS,
        FIELD.IMAGE_MANIPULATION,
        FIELD.ONLINE_DUPLICATE,
        FIELD.EVIDENCE_HOSTNAME,
        FIELD.EVIDENCE_THUMBNAIL_URL,
    ),
    ID_PROCESSOR.FR_DRIVER_LICENSE_PROCESSOR: COMMON_FIELDS,
    ID_PROCESSOR.FR_NATIONAL_ID_PROCESSOR: (*COMMON_FIELDS, FIELD.ADDRESS),
    ID_PROCESSOR.FR_PASSPORT_PROCESSOR: (
        *COMMON_FIELDS,
        FIELD.ADDRESS,
        FIELD.PLACE_OF_BIRTH,
    ),
    ID_PROCESSOR.AU_DRIVER_LICENSE_PROCESSOR: (
        FIELD.FULL_NAME,
        FIELD.ADDRESS,
        FIELD.DOC_ID,
        FIELD.EXPIRATION_DATE,
        FIELD.DATE_OF_BIRTH,
        FIELD.ADMINISTRATIVE_AREA,
    ),
    ID_PROCESSOR.DE_DRIVER_LICENSE_PROCESSOR: (
        FIELD.FAMILY_NAME,
        FIELD.GIVEN_NAME,
        FIELD.DATE_OF_BIRTH,
        FIELD.PLACE_OF_BIRTH,
        FIELD.ISSUE_DATE,
        FIELD.ISSUE_AUTHORITY,
        FIELD.EXPIRATION_DATE,
        FIELD.DOC_ID,
    ),
    ID_PROCESSOR.DE_PASSPORT_PROCESSOR: (
        FIELD.DOC_ID,
        FIELD.FAMILY_NAME,
        FIELD.GIVEN_NAME,
        FIELD.DATE_OF_BIRTH,
        FIELD.PLACE_OF_BIRTH,
        FIELD.ISSUE_DATE,
        FIELD.EXPIRATION_DATE,
        FIELD.ISSUE_AUTHORITY,
        FIELD.ADDRESS,
    ),
    ID_PROCESSOR.IN_DRIVER_LICENSE_PROCESSOR: (
        FIELD.DOC_ID,
        FIELD.FULL_NAME,
        FIELD.FATHER_NAME,
        FIELD.ADDRESS,
        FIELD.DATE_OF_BIRTH,
        FIELD.ISSUE_DATE,
        FIELD.EXPIRATION_DATE,
        FIELD.ISSUE_AUTHORITY,
    ),
    ID_PROCESSOR.IN_PASSPORT_PROCESSOR: (
        FIELD.DOC_ID,
        FIELD.FAMILY_NAME,
        FIELD.GIVEN_NAME,
        FIELD.SEX,
        FIELD.DATE_OF_BIRTH,
        FIELD.PLACE_OF_BIRTH,
        FIELD.PLACE_OF_ISSUE,
        FIELD.ISSUE_DATE,
        FIELD.EXPIRATION_DATE,
    ),
    # Permanent Account Number (PAN): ten-character alphanumeric identifier,
    # issued  by the Indian Income Tax Department
    ID_PROCESSOR.IN_TAX_CARD_PROCESSOR: (
        FIELD.DOC_ID,
        FIELD.FULL_NAME,
        FIELD.FATHER_NAME,
        FIELD.DATE_OF_BIRTH,
    ),
    ID_PROCESSOR.IN_VOTER_ID_PROCESSOR: (
        FIELD.DOC_ID,
        FIELD.FULL_NAME,
        FIELD.FATHER_NAME,
        FIELD.DATE_OF_BIRTH,
        FIELD.ISSUE_DATE,
    ),
    # Aadhaar is a verifiable 12-digit identification number for residents of India
    ID_PROCESSOR.IN_AADHAR_CARD_PROCESSOR: (
        FIELD.DOC_ID,
        FIELD.FULL_NAME,
        FIELD.DATE_OF_BIRTH,
        FIELD.ISSUE_DATE,
        FIELD.FATHER_NAME,
        FIELD.HUSBAND_NAME,
    ),
}

# Mapping for field name convention changes
PROCESSOR_FIELD_REPLACEMENTS = {
    ID_PROCESSOR.FR_PASSPORT_PROCESSOR: {FIELD.GIVEN_NAMES: FIELD.GIVEN_NAME},
}

# Snake case convention is being adopted for identity processor field names
# These legacy processors are still using mixed-capitalization-with-spaces fields
LEGACY_NON_SNAKE_CASE_PROCESSORS = (
    ID_PROCESSOR.US_DRIVER_LICENSE_PROCESSOR,
    ID_PROCESSOR.US_PASSPORT_PROCESSOR,
    ID_PROCESSOR.FR_DRIVER_LICENSE_PROCESSOR,
    ID_PROCESSOR.FR_NATIONAL_ID_PROCESSOR,
)
