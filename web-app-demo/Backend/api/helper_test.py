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

""" Backend Unit Tests"""

import os
from typing import Dict
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from google.cloud import documentai_v1beta3 as docai
from helper import process_document  # pylint: disable=E0401

processor_id_by_processor_type: Dict[str, str] = {"OCR": "6d7af7fc640a7219"}

PROCESSOR_TYPE = "processor-type"

PROJECT_ID = "project-id"
LOCATION = "location"
PROCESSOR_ID = "processor-id"


class TestHelper(unittest.TestCase):
    """Testing helper functions"""

    @patch("helper.DocumentProcessorServiceClient")
    # pylint: disable=no-self-use
    def test_process_document_normal(self, process_document_mock):
        """Tests process document in a normal case"""

        mocked_client_instance = MagicMock()

        # Mock process document API call to use a fake API response
        mocked_client_instance.process_document.return_value = (
            docai.types.ProcessResponse(
                document=docai.types.Document(
                    entities=[
                        docai.types.Document.Entity(
                            page_anchor=docai.types.Document.PageAnchor(
                                page_refs=[
                                    docai.types.Document.PageAnchor.PageRef(page=0),
                                    docai.types.Document.PageAnchor.PageRef(page=1),
                                ]
                            )
                        )
                    ]
                )
            )
        )

        process_document_mock.return_value = mocked_client_instance

        __location__ = os.path.realpath(
            os.path.join(os.getcwd(), os.path.dirname(__file__))
        )

        process_document_request = {
            "project_id": PROJECT_ID,
            "location": LOCATION,
            "file_path": os.path.join(__location__, "test_docs/file"),
            "file_type": "application/pdf",
            "processor_id": PROCESSOR_ID,
        }

        processor_response = docai.types.ProcessResponse()
        processor_response.document = docai.types.Document()
        resp = process_document(process_document_request)
        self.assertIn("document", str(resp))


if __name__ == "__main__":
    unittest.main()
