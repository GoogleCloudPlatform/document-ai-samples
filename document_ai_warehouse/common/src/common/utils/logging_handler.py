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
import os

"""class and methods for logs handling."""

import logging

import google.cloud.logging_v2

logging_client = google.cloud.logging_v2.Client()
logging_client.get_default_handler()
logging_client.setup_logging()

logging.basicConfig(level=logging.INFO)
# utility to get stdout when running locally utility testing scripts
STDOUT = os.environ.get("DEBUG", None)


class Logger:
    """class def handling logs."""

    @staticmethod
    def info(message):
        """Display info logs."""
        logging.info(message)
        if STDOUT:
            print(message)

    @staticmethod
    def warning(message):
        """Display warning logs."""
        logging.warning(message)
        if STDOUT:
            print(message)

    @staticmethod
    def error(message):
        """Display error logs."""
        logging.error(message)
        if STDOUT:
            print(message)

    @staticmethod
    def debug(message):
        """Display debug logs."""
        logging.debug(message)
        if STDOUT:
            print(message)
