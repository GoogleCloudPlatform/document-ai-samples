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

from typing import Optional


class ConversionError:
    error_type_conversion = "TYPE_CONVERSION"
    error_type_bq_insert = "BQ_INSERT"
    error_type_exclude_field = "BQ_FIELD_EXCLUSION"
    error_type_duplicate_field = "DUPLICATE_FIELD"

    def __init__(
        self,
        key: str,
        value,
        error,
        error_message,
        error_type,
        identifier: Optional[str] = None,
    ):
        self.key = key
        self.value = value
        self.error = error
        self.error_message = error_message
        self.error_type = error_type
        self.identifier = identifier

    def __str__(self):
        return (
            f"ConversionError key is {self.key} value is {self.value} error is {self.error} "
            f"error_message is {self.error_message} and error_type is {self.error_type} and id is {self.identifier}"
        )

    def __repr__(self):
        return (
            f"ConversionError(key={self.key}, value={self.value}, error={self.error}, "
            f"error_message={self.error_message}, error_type={self.error_type}, id={self.identifier})"
        )

    def to_dict(self):
        return {
            "type": self.error_type,
            "field": self.key,
            "value": self.value,
            "error": self.error,
            "message": self.error_message,
        }
