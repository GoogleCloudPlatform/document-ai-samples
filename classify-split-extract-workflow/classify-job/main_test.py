# Copyright 2024 Google LLC
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

""" Helper function to test locally Classification/Splitting processing """

import config
from logging_handler import Logger

from main import process

logger = Logger.get_logger(__file__)

if __name__ == "__main__":
    # To be used for testing from the local machine. Specify the file to trigger processing
    # Either a single file like below (must be located in GCS: gs://PROJECT_ID--documents/)
    config.INPUT_FILE = "taxes-combined.pdf"
    # Or a path to the folder to trigger batch processing using START_PIPLEINE trigger file:
    config.INPUT_FILE = f"combined/{config.START_PIPELINE_FILENAME}"

    process()
