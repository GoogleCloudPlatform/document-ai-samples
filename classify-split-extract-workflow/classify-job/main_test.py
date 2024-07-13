#!/usr/bin/env python3

"""
Copyright 2024 Google LLC

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

import config
from logging_handler import Logger
from main import process

logger = Logger.get_logger(__file__)


if __name__ == "__main__":
  # config.INPUT_FILE = "bsc-dme-pa-form.pdf"
  config.INPUT_FILE = "blank-combined_6.pdf"
  #config.INPUT_FILE = "CLINICAL NOTES 1.pdf"
  config.INPUT_FILE = f"taxes/{config.START_PIPELINE_FILENAME}"
  config.INPUT_FILE = f"combined/{config.START_PIPELINE_FILENAME}"
  process()
