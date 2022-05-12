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
import unittest
from typing import Dict
from unittest.mock import patch

import google.auth
from google.cloud import documentai_v1beta3 as docai

from helper import process_document  # pylint: disable=E0401

_, project_id = google.auth.default()
LOCATION = "us"  # Format is 'us' or 'eu'

processor_id_by_processor_type: Dict[str, str] = {"OCR": "6d7af7fc640a7219"}


class TestHelper(unittest.TestCase):
    """Testing helper functions"""

    @patch("helper.documentai.DocumentProcessorServiceClient.process_document")
    def test_process_document_normal(self, process_document_mock):
        """Tests process document in a normal case"""

        __location__ = os.path.realpath(
            os.path.join(os.getcwd(), os.path.dirname(__file__))
        )

        process_document_request = {
            "project_id": project_id,
            "location": LOCATION,
            "processor_type": "OCR",
            "file_path": os.path.join(__location__, "test_docs/file"),
            "file_type": "application/pdf",
        }

        processor_response = docai.types.ProcessResponse()
        processor_response.document = docai.types.Document()
        process_document_mock.return_value = processor_response
        resp = process_document(
            process_document_request, processor_id_by_processor_type
        )
        self.assertIn("document", str(resp))

    @patch("helper.documentai.DocumentProcessorServiceClient.process_document")
    def test_process_document_error(self, process_document_mock2):
        """Tests process document in a normal case"""

        __location__ = os.path.realpath(
            os.path.join(os.getcwd(), os.path.dirname(__file__))
        )

        process_document_request = {
            "project_id": project_id,
            "location": LOCATION,
            "processor_type": "OCR",
            "file_path": os.path.join(__location__, "test_docs/file"),
            "file_type": "application/pdf",
        }

        processor_response = docai.types.ProcessResponse()
        processor_response.document = docai.types.Document()
        process_document_mock2.side_effect = Exception("Error")
        resp = process_document(
            process_document_request, processor_id_by_processor_type
        )
        self.assertIn("ERROR", str(resp))


if __name__ == "__main__":
    unittest.main()
