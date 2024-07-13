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

import logging
import os
import sys
import google.cloud.logging

"""class and methods for logs handling.
Sample usage:
>>> from common.utils.logging_handler import logger

>>> logger.get_logger(__file__)

>>> def my_function(){
>>>   logger.info("")
>>> }
"""
# TODO For Cloud Run Job, this needs additional setup for the Resource handling
# See: https://stackoverflow.com/questions/74302649/log-to-cloud-logging-with-correct-severity-from-cloud-run-job-and-package-used-i

CLOUD_LOGGING_ENABLED = True
if CLOUD_LOGGING_ENABLED:
    client = google.cloud.logging.Client()
    client.setup_logging()
    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(message)s",
                        level=logging.INFO)
else:
    logging.basicConfig(level=logging.INFO)


class Logger:
    """class def handling logs."""

    def __init__(self, name):
        dirname = os.path.dirname(name)
        filename = os.path.split(name)[1]
        folder = os.path.split(dirname)[1]
        module_name = f"{folder}/{filename}"
        self.logger = logging.getLogger(module_name)
        handler = logging.StreamHandler(sys.stdout)
        log_format = "%(levelname)s: [%(name)s:%(lineno)d - " \
                     "%(funcName)s()] %(message)s"
        handler.setFormatter(logging.Formatter(log_format))
        self.logger.addHandler(handler)
        self.logger.propagate = False

    @classmethod
    def get_logger(cls, name) -> logging.Logger:
        logger_instance = cls(name)
        return logger_instance.logger
