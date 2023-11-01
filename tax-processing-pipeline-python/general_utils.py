# Copyright 2022 Google LLC
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

"""General Utility Functions"""

import yaml


def read_yaml(file_path):
    """
    Reads a yaml file and returns a dictionary
    """
    with open(file_path, "r", encoding="utf8") as file:
        return yaml.safe_load(file)


def write_yaml(file_path, data):
    """
    Writes a yaml file from a dictionary
    """
    with open(file_path, "w", encoding="utf8") as file:
        yaml.dump(data, file)


def invert_dictionary_with_array(dictionary: dict):
    """
    Inverts a dictionary with arrays as values
    e.g. {key: [value1, value2]} -> {value1: key, value2: key}
    """
    return {value: key for key, values in dictionary.items() for value in values}
