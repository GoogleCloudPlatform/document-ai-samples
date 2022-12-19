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
from typing import List

from docai_bq_connector.helper import find


class DocumentField:
    def __init__(
        self,
        name: str,
        value: str,
        normalized_value,
        confidence: float,
        page_number: int,
    ):
        self.name = name
        self.value = value
        self.normalized_value = normalized_value
        self.confidence = confidence
        self.page_number = page_number
        self.children: List[DocumentRow] = []

    def to_bigquery_safe_name(self):
        return self.name.replace("-", "_")

    def __repr__(self):
        return (
            f"DocumentField(name: {self.name}, value: {self.value}, "
            f"confidence: {self.confidence}, page_number: {self.page_number})"
        )

    def to_dictionary(self) -> dict:
        _dictionary = {
            "name": self.to_bigquery_safe_name(),
            "value": self.value,
            "confidence": self.confidence,
            "page_number": self.page_number,
        }
        if self.children and len(self.children) > 0:
            _children = []
            for child_row in self.children:
                _fields = []
                for child_field in child_row.fields:
                    _fields.append(child_field.to_dictionary())
                _children.append(_fields)
            _dictionary["children"] = _children
        return _dictionary


class DocumentRow:
    def __init__(self):
        self.fields: [DocumentField] = []

    def find_field_by_name(self, name: str) -> DocumentField:
        return find(lambda field: field.name == name, self.fields)

    def __repr__(self):
        return f"DocumentRow({self.fields})"
