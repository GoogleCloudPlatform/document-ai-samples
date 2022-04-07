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

"""Cloud Firestore Utility Functions"""

from google.cloud import firestore


def save_to_firestore(project_id: str, collection: str, document_id: str, data: dict):
    """
    Saves data to Firestore.
    """
    firestore_client = firestore.Client(project_id)
    doc_ref = firestore_client.collection(collection).document(document_id)
    doc_ref.set(data)


def read_collection(project_id: str, collection: str) -> dict:
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


def delete_collection(project_id: str, collection: str):
    """
    Deletes all documents from a collection in Firestore.
    """
    firestore_client = firestore.Client(project_id)

    collection_ref = firestore_client.collection(collection)
    docs = collection_ref.stream()

    for doc in docs:
        doc.reference.delete()
