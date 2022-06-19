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

"""Document AI PDF Splitter Sample Unit Tests"""

import os
import argparse
import unittest
import tempfile
import shutil
from unittest.mock import MagicMock, patch

from google.cloud import documentai_v1beta3 as docai

from main import main

PROCESSOR_TYPE = "processor-type"

PROJECT_ID = "project-id"
LOCATION = "location"
PROCESSOR_ID = "processor-id"
PROCESSOR_NAME = f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}"

TEST_FILENAME = "multi_document.pdf"
EXPECTED_FILENAME = "subdoc_1_of_1_multi_document.pdf"


class TestMain(unittest.TestCase):
    """Test class for Document AI PDF splitter sample"""

    @patch("main.DocumentProcessorServiceClient")
    def test_split_document(self, mocked_client):
        """Test for Document AI PDF splitter sample"""

        # Create a mocked client instance to mock methods used by main.py
        mocked_client_instance = MagicMock()

        # Mock list processor API call to get a fake processor to use
        mocked_client_instance.list_processors.return_value = docai.types.ListProcessorsResponse(
            processors=[
                docai.types.Processor(
                    type_=PROCESSOR_TYPE,
                    name="projects/PROJECT_ID/locations/LOCATION/processors/PROCESSOR_ID",
                )
            ]
        )

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

        # Use mocked client instance as the mocked client
        mocked_client.return_value = mocked_client_instance

        # Get path to multi_document.pdf test file
        dir_path = os.path.dirname(os.path.realpath(__file__))
        test_filepath = os.path.join(dir_path, TEST_FILENAME)

        # Create temporary directory to add test files to
        temp_out_dir = tempfile.mkdtemp()

        # Call main function with args
        main(
            argparse.Namespace(
                input=test_filepath,
                output_dir=temp_out_dir,
                project_id=PROJECT_ID,
                multi_region_location=LOCATION,
                split_processor_type=PROCESSOR_TYPE,
            )
        )

        expected_filepath = os.path.join(temp_out_dir, EXPECTED_FILENAME)

        # Check to see that a split file was created
        assert os.path.isfile(expected_filepath)

        # Check to see that the file is not empty
        filesize = os.path.getsize(expected_filepath)
        assert filesize > 0

        # Clean up test files
        shutil.rmtree(temp_out_dir)


if __name__ == "__main__":
    unittest.main()
