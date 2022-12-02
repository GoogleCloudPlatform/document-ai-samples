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

    def get_table_schema(self, table_id: str):
        table_ref = bigquery.TableReference(self.dataset_ref, table_id)
        table = self.client.get_table(table_ref)
        return table.schema
