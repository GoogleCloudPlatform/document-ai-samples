#
# Copyright 2022 Google LLC
#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import logging

from google.cloud import bigquery
from google.cloud.exceptions import NotFound


class StorageManager:
    def __init__(self, project_id: str, dataset_id: str):
        self.project_id = project_id
        self.dataset_id = dataset_id

        self.client: bigquery.client.Client = None
        if project_id is None:
            self.client = bigquery.Client()
            self.project_id = self.client.project
        else:
            self.client = bigquery.Client(project=project_id)

        self.dataset_ref = bigquery.DatasetReference(self.project_id, self.dataset_id)

    def _does_dataset_exist(self, dataset_ref) -> bool:
        try:
            self.client.get_dataset(dataset_ref)
            logging.debug("Dataset %s already exists", dataset_ref)
            return True
        except NotFound:
            logging.debug("Dataset %s is not found", dataset_ref)
            return False

    def does_table_exist(self, name):
        table_ref = bigquery.TableReference(self.dataset_ref, name)
        try:
            self.client.get_table(table_ref)
            logging.debug("Table %s already exists.", table_ref.table_id)
            return True
        except NotFound:
            logging.debug("Table %s is not found.", table_ref.table_id)
            return False

    def write_record(self, table_id: str, record):
        table_ref = bigquery.TableReference(self.dataset_ref, table_id)
        errors = self.client.insert_rows_json(table_ref, [record])
        if errors:
            logging.error("Encountered errors while inserting rows: %s", errors)
        return errors

    def update_record(
        self, table_id: str, record_id_name, record_id_value, cols_to_update
    ):
        # Assumes all columns and key are of type STRING
        query_params = []
        dml_statement = f"UPDATE `{self.project_id}.{self.dataset_id}.{table_id}` SET"
        if len(cols_to_update) == 0:
            # Nothing to do
            return
        idx = 0
        for index, (cur_col, cur_val) in enumerate(cols_to_update.items()):
            dml_statement = f"{dml_statement} {cur_col} = @param_{idx},"
            cur_qp = bigquery.ScalarQueryParameter(f"param_{idx}", "STRING", cur_val)
            query_params.append(cur_qp)
            idx += 1
        # Remove last comma
        dml_statement = (
            f"{dml_statement[:-1]} WHERE {record_id_name} = @param_record_id"
        )
        cur_qp = bigquery.ScalarQueryParameter(
            "param_record_id", "STRING", record_id_value
        )
        query_params.append(cur_qp)

        logging.debug(
            f"About to run query: {dml_statement} with params: {query_params}"
        )
        query_job_config = bigquery.QueryJobConfig(
            use_legacy_sql=False, query_parameters=query_params
        )
        query_job = self.client.query(query=dml_statement, job_config=query_job_config)
        query_job.result()

    def get_records(self, query: str, query_params=[]):
        # Only supports scalar parameters
        bq_q_params = []
        for qp in query_params:
            logging.debug(qp)
            cur_p = bigquery.ScalarQueryParameter(qp["name"], qp["type"], qp["value"])
            bq_q_params.append(cur_p)
        logging.debug(f"About to run query: {query} with params: {bq_q_params}")
        query_job_config = bigquery.QueryJobConfig(
            use_legacy_sql=False, query_parameters=bq_q_params
        )
        query_job = self.client.query(query=query, job_config=query_job_config)

        bq_rows = query_job.result()
        # Convert to array of dict
        records = [dict(row) for row in bq_rows]
        logging.debug(f"Will return {records}")
        return records

    def get_table_schema(self, table_id: str):
        table_ref = bigquery.TableReference(self.dataset_ref, table_id)
        table = self.client.get_table(table_ref)
        return table.schema
