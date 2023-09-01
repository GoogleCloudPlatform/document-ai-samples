"""
Copyright 2023 Google LLC

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


import re
import os
import pandas as pd


def split_uri_2_bucket_prefix(uri: str):
  match = re.match(r"gs://([^/]+)/(.+)", uri)
  if not match:
    # just bucket no prefix
    match = re.match(r"gs://([^/]+)", uri)
    return match.group(1), ""
  bucket = match.group(1)
  prefix = match.group(2)
  return bucket, prefix


def split_uri_2_path_filename(uri: str):
  dirs = os.path.dirname(uri)
  file_name = os.path.basename(uri)
  return dirs, file_name


def get_processor_location(processor_path):
  m = re.match(r'projects/(.+)/locations/(.+)/processors', processor_path)
  if m and len(m.groups()) >= 2:
    return m.group(2)

  return None


def is_date(string: str):
  """
  Return whether the string can be interpreted as a date.
  """
  try:
    converted = pd.to_datetime(string)
    return True

  except Exception:
    return False

