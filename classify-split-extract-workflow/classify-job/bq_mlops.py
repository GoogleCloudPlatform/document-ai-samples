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

# pylint: disable=import-error
"""
BigQuery MLOps helper functions for managing tables and models.

This module includes functions for creating external tables, checking and creating
BigQuery tables, and creating or replacing remote models using Document AI processors.
"""
# pylint: disable=logging-fstring-interpolation

from typing import List, Optional

from config import BQ_DATASET_ID_MLOPS
from config import BQ_GCS_CONNECTION_NAME
from config import BQ_OBJECT_TABLE_RETENTION_DAYS
from config import BQ_PROJECT_ID
from config import BQ_REGION
from config import PROJECT_ID
from google.api_core.exceptions import NotFound
from google.cloud import bigquery
from google.cloud.documentai_v1 import Processor
from logging_handler import Logger
from utils import get_utc_timestamp

# BigQuery client
bq = bigquery.Client(project=PROJECT_ID)
logger = Logger.get_logger(__file__)


def object_table_create(
    f_uris: List[str],
    document_type: str,
    table_suffix: str = get_utc_timestamp(),
    retention_days: int = BQ_OBJECT_TABLE_RETENTION_DAYS,
) -> str:
    """
    Creates an external table in BigQuery to store document URIs.

    Args:
        f_uris (List[str]): List of file URIs.
        document_type (str): Type of the document.
        table_suffix (str, optional): Suffix for the table name. Defaults to current UTC timestamp.
        retention_days (int, optional): Number of days before the table expires.
        Defaults to BQ_OBJECT_TABLE_RETENTION_DAYS.

    Returns:
        str: The name of the created BigQuery table.
    """

    uris = "', '".join(f_uris)
    object_table_name = (
        f"{BQ_PROJECT_ID}.{BQ_DATASET_ID_MLOPS}."
        f"{document_type.upper()}_DOCUMENTS_{table_suffix}"
    )
    query = f"""
    CREATE OR REPLACE EXTERNAL TABLE `{object_table_name}`
        WITH CONNECTION `{BQ_PROJECT_ID}.{BQ_REGION}.{BQ_GCS_CONNECTION_NAME}`
        OPTIONS(
            object_metadata = 'SIMPLE',
            metadata_cache_mode = 'AUTOMATIC',
            uris = ['{uris}'],
            max_staleness = INTERVAL 1 DAY,
            expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL {retention_days} DAY)
        )
    """

    job = bq.query(query=query)
    job.result()
    logger.info(f"Created external table {object_table_name}")
    return object_table_name


def table_create(table_id: str) -> None:
    """
    Checks if a BigQuery table exists, and if not, creates it.

    Args:
        table_id (str): The BigQuery table ID.
    """

    try:
        bq.get_table(table_id)  # Make an API request.
        logger.info(f"Table {table_id} already exists.")
    except NotFound:
        table = bigquery.Table(table_id)
        table = bq.create_table(table)  # Make an API request.
        logger.info(f"Created table {table.table_id}.")


def remote_model_create(processor: Processor, model_name: Optional[str] = None) -> None:
    """
    Creates or replaces a remote model in BigQuery using a Document AI processor.

    Args:
        processor (Processor): Document AI processor.
        model_name (str, optional): The name of the model. Defaults to a name based on processor.
    """

    if not model_name:
        model_name = (
            f"{BQ_PROJECT_ID}.{BQ_DATASET_ID_MLOPS}.{processor.name.upper()}_MODEL"
        )
    query = f"""
    CREATE OR REPLACE MODEL `{model_name}`
        REMOTE WITH CONNECTION `{BQ_PROJECT_ID}.{BQ_REGION}.{BQ_GCS_CONNECTION_NAME}`
        OPTIONS(
            REMOTE_SERVICE_TYPE = 'cloud_ai_document_v1',
            DOCUMENT_PROCESSOR = "{processor.default_processor_version}"
        )
    """
    job = bq.query(query=query)
    job.result()
    logger.info(f"Created or replaced remote model {model_name}")
