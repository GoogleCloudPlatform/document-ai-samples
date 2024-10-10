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

# pylint: disable=logging-fstring-interpolation,broad-exception-caught

""" Main function to run Cloud Run job Classification/Splitting tasks """

import os

import config
from config import CLASSIFIER
from config import FULL_JOB_NAME
from docai_helper import get_processor_and_client
from gcs_helper import get_list_of_uris
from logging_handler import Logger
from split_and_classify import batch_classification
from split_and_classify import handle_no_classifier
from split_and_classify import save_classification_results
from split_and_classify import stream_classification_results

logger = Logger.get_logger(__file__)


def process():
    """Main function for the Classifier/Splitter Cloud Run Job"""
    input_bucket = config.CLASSIFY_INPUT_BUCKET
    input_file = config.INPUT_FILE

    out_bucket_name = None
    out_file_name = None

    logger.info(f"Processing documents on event gs://{input_bucket}/{input_file} ")
    logger.info(f"FULL_JOB_NAME={FULL_JOB_NAME}")
    logger.info(f"CLOUD_RUN_EXECUTION={os.getenv('CLOUD_RUN_EXECUTION')}")

    try:
        processor, dai_client = get_processor_and_client(CLASSIFIER)
        f_uris = get_list_of_uris(input_bucket, input_file)

        # When classifier/splitter is not setup
        if not processor:
            logger.info(f"{CLASSIFIER} processor not found in the config.json")
            classified_items = handle_no_classifier(f_uris)
        else:
            # Run Classification job
            logger.info(
                f"Using {processor.name} processor for Classification/Splitting"
            )
            classified_items = batch_classification(processor, dai_client, f_uris)

        logger.info(f"Classified items: {classified_items}")
        out_bucket_name, out_file_name = save_classification_results(classified_items)

    except Exception as e:
        logger.error(f"Error during batch classification: {e}")

    stream_classification_results(
        call_back_url=config.CALL_BACK_URL,
        bucket_name=out_bucket_name,
        file_name=out_file_name,
    )


if __name__ == "__main__":
    process()
