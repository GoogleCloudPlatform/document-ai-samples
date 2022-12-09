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

from datetime import datetime
import logging
from typing import Dict

# Indicates the metadata types that can be mapped - Informational only
metadata_to_map = ["file_name", "doc_status", "doc_type", "doc_event_id", "doc_group_id", "hitl_operation_id","created_at", "updated_at"]

# Class holding information about how to map a specific metadata type
class BqMetadataMappingInfo:
    def __init__(
        self,
        bq_column_name: str, # The column in BQ this metadata will be mapped to
        metadata_value: any = None,  # If set, this value will be used for the column. If not set, a default value will be used if possible
        skip_map: bool = False, # If set this particular metadata will NOT be mapped into a BQ column
    ):  
        self.bq_column_name = bq_column_name
        self.metadata_value = metadata_value
        self.skip_map = skip_map

    def __str__ (self):
        return f'bq_column_name={self.bq_column_name}, metadata_value={self.metadata_value}, skip_map = {self.skip_map}'

    def set_metadata_value_if_not_already_set(self, metadata_value):
        if self.metadata_value is None:
           self.metadata_value = metadata_value

    def map_to_bq_col_and_value(self):
        if not self.skip_map:
            return self.bq_column_name, self.metadata_value
        else:
            return None, None

def _generate_default_value(metadata_name):
    if metadata_name in ['created_at','updated_at']:
        return datetime.now().isoformat()
    else:
        return None


# This mapper class allows flexibility in schema column names for metadata to be added in BQ
class BqMetadataMapper:
    def __init__(
        self,
        mapping_info: Dict[str, BqMetadataMappingInfo],
        
    ):
        self.mapping_info = mapping_info
        # Add default mappings for any missing metadata, using the same name for the BigQuery column
        for cur_metadata in metadata_to_map:
            if not cur_metadata in self.mapping_info:
                logging.debug(f"Adding default mapping for metadata = {cur_metadata}")
                self.mapping_info[cur_metadata] = BqMetadataMappingInfo(bq_column_name=cur_metadata)

    def __str__ (self):
        out_str = ""
        for k,v in self.mapping_info.items():
            out_str = f'{out_str} metadata = {k} - mapping_info = {v}'
        return out_str

    def set_default_value_for_metadata_if_not_set(self, metadata_name, new_default_value):
        mapping_info = self.mapping_info.get(metadata_name)
        if not mapping_info is None:
            mapping_info.set_metadata_value_if_not_already_set(new_default_value)

    # Return and array of column name and value
    def map_metadata(self):
        response = []
        for cur_metadata_name, cur_mapping_info_config in self.mapping_info.items():
            mapping_for_cur_metadata = {}
            bq_col_name, bq_col_value = cur_mapping_info_config.map_to_bq_col_and_value()
            if not bq_col_name is None:
                mapping_for_cur_metadata["bq_column_name"] = bq_col_name
                if bq_col_value is None:
                    mapping_for_cur_metadata["bq_column_value"] = _generate_default_value(cur_metadata_name)
                else:
                    mapping_for_cur_metadata["bq_column_value"] = bq_col_value
                response.append(mapping_for_cur_metadata)
        
        return response


