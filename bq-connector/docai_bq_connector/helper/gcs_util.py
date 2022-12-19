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

from google.cloud import storage


def get_gcs_blob(bucket_name, file_name):
    try:
        gcs_client = storage.Client()
        bucket = gcs_client.get_bucket(bucket_name)
        gcs_file = bucket.get_blob(file_name)
        file_meta = gcs_file.metadata
        file_blob: bytes = gcs_file.download_as_bytes()
        logging.info("Fetched file from GCS successfully.")
        return file_blob, file_meta
    except Exception as err:
        raise Exception(
            f"Cannot get file {file_name} from bucket {bucket_name}. Error: {err}"
        )


def write_gcs_blob(bucket_name, file_name, content_as_str, content_type):
    gcs_client = storage.Client()
    bucket = gcs_client.get_bucket(bucket_name)
    gcs_file = bucket.blob(file_name)
    gcs_file.upload_from_string(content_as_str, content_type=content_type)
    logging.debug(f"Saving the file {file_name} to GCS.")
