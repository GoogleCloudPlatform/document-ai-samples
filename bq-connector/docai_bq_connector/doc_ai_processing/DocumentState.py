from enum import Enum


class DocumentState(Enum):
    submission_received = "SUBMISSION_RECEIVED"
    document_extraction_complete = "DOCUMENT_EXTRACTION_COMPLETE"
    submitted_for_hitl = "SUBMITTED_FOR_HITL"
    hitl_review_complete = "HITL_REVIEW_COMPLETE"
    document_processing_complete = "DOCUMENT_PROCESSING_COMPLETE"
    unknown = "UNKNOWN"

    @classmethod
    def _missing_(cls, value):
        return DocumentState.unknown

    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value
