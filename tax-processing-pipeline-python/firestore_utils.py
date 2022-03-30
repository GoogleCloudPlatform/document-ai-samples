"""
Cloud Firestore Utility Functions
"""
from google.cloud import firestore


def save_to_firestore(
    project_id: str, collection: str, document_id: str, data: dict
):
    """
    Processes a single document from GCS using the Document AI Synchronous API.
    """
    firestore_client = firestore.Client(project_id)
    doc_ref = firestore_client.collection(collection).document(document_id)
    doc_ref.set(data)


def get_all_data_from_firestore_collection(
    project_id: str, collection: str
) -> dict:
    """
    Outputs all documents from a collection in Firestore as a dictionary.
    Format:
    {
        document_id: {
            field_name: field_value
        }
    }
    """
    firestore_client = firestore.Client(project_id)

    collection_ref = firestore_client.collection(collection)
    docs = collection_ref.stream()
    data = {}

    for doc in docs:
        data[doc.id] = doc.to_dict()

    return data
