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
import json
import traceback
from typing import Any
from typing import Dict
from typing import List

import pandas as pd
import proto
from google.cloud import contentwarehouse_v1
from google.type import datetime_pb2

from common.utils.document_ai_utils import get_key_values_dic
from common.utils.logging_handler import Logger
from .document_warehouse_utils import DocumentWarehouseUtils


def get_key_value_pairs(document_ai_output):
  json_string = proto.Message.to_json(document_ai_output)
  data = json.loads(json_string)
  document_entities: Dict[str, Any] = {}
  for entity in data.get('entities'):
    get_key_values_dic(entity, document_entities)

  names = []
  for key in document_entities.keys():
    for val in document_entities[key]:
      if len(val) == 2:  # Flat Labels
        key_name = key
        key_value = val[0]
      elif len(val) == 3:  # Nested Labels
        key_name = val[0]
        key_value = val[1]
      else:
        continue

      if key_name not in [x[0] for x in names]:  # Filter duplicates
        names.append((key_name, key_value))
  return names


def extract_entities_as_properties(
        document_schema: contentwarehouse_v1.DocumentSchema,
        entities: Dict[str, List[any]],
        key_names: Dict[str, str]):
    properties = []

    for property in document_schema.property_definitions:
        if property.name.lower() in key_names:
            key = key_names[property.name.lower()]
            values = entities[key]
            one_property = contentwarehouse_v1.Property()
            one_property.name = property.name

            try:
                if 'integer_type_options' in property:
                    one_property.integer_values.values[:] = [int(v) for v in values]

                elif 'float_type_options' in property:
                    one_property.float_values.values[:] = [float(v) for v in values]

                elif 'text_type_options' in property:
                    one_property.text_values.values[:] = values

                elif 'date_time_type_options' in property:
                    one_property.date_time_values.values[:] = values

                # TODO: handle 'enum_type_options' and 'timestamp_type_options'

                properties.append(one_property)
            except Exception as e:
                # Skip adding this property if the value does not fit to the type
                print(str(e))

    return properties

from google.protobuf.json_format import MessageToJson
def get_metadata_properties(key_values, schema) -> List[
  contentwarehouse_v1.Property]:
  def get_type_using_schema(property_name):
    for prop in schema.property_definitions:
        if prop.name == property_name:
            for t in ["text_type_options", "date_time_type_options",
                      "float_type_options", "integer_type_options", ]:
                if t in prop:
                    return t
    return None
  metadata_properties = []

  for key, value in key_values:
    value_type = get_type_using_schema(key)
    if value_type is not None:
      Logger.info(f"get_metadata_properties key={key}, value={value}, type={value_type}")
      one_property = contentwarehouse_v1.Property()
      one_property.name = key

      try:
        if value_type == "text_type_options":
          one_property.text_values = contentwarehouse_v1.TextArray(values=[str(value)])
        elif value_type == "float_type_options":
          one_property.float_values = contentwarehouse_v1.FloatArray(
              values=[float(value)])
        elif value_type == "integer_type_options":
          one_property.integer_values = contentwarehouse_v1.IntegerArray(
              values=[int(value)])
        elif value_type == "date_time_type_options":
          date_time = pd.to_datetime(value)

          dt = datetime_pb2.DateTime(year=date_time.year,
                                     month=date_time.month,
                                     day=date_time.day,
                                     hours=date_time.hour,
                                     minutes=date_time.minute,
                                     seconds=date_time.second,
                                     utc_offset={})
          one_property.date_time_values = contentwarehouse_v1.DateTimeArray(values=[dt])
        else:
          Logger.warning(
              f"Unsupported property type {value_type} for  {key} = {value} Skipping. ")
          continue
        metadata_properties.append(one_property)

      except Exception as ex:
        Logger.warning(f"Could not load {key} = {value} of type {value_type} as property. Skipping. Exception = {ex}")
        continue
    else:
      Logger.warning((f"get_metadata_properties key={key}, value={value}, Type not detected"))


  return metadata_properties


def process_document(project_number: str,
                     api_location: str,
                     folder_id: str,
                     display_name: str,
                     document_schema_id: str,
                     caller_user: str,
                     bucket_name: str, document_path: str,
                     document_ai_output):
  try:
    Logger.info(f"process_document with project_number={project_number}, "
                f"api_location={api_location}, folder_id={folder_id}, "
                f"display_name={display_name}, document_schema_id="
                f"{document_schema_id}, caller_user={caller_user}, "
                f"bucket_name={bucket_name}, document_path={document_path}")
    dw_utils = DocumentWarehouseUtils(project_number=project_number,
                                      api_location=api_location)

    schema = dw_utils.get_document_schema(document_schema_id)
    keys = get_key_value_pairs(document_ai_output)
    metadata_properties = get_metadata_properties(keys, schema)

    create_document_response = dw_utils.create_document(
        display_name=display_name,
        mime_type="application/pdf",
        document_schema_id=document_schema_id,
        raw_document_path=f"gs://{bucket_name}/{document_path}",
        docai_document=document_ai_output,
        caller_user_id=caller_user,
        metadata_properties=metadata_properties)

    Logger.info(f"process_document create_document_response"
                f"={create_document_response}")
    if create_document_response is not None:
      document_id = create_document_response.document.name.split("/")[-1]

      # TODO how to link one document to multiple folders
      link_document_response = dw_utils.link_document_to_folder(
          document_id=document_id,
          folder_document_id=folder_id,
          caller_user_id=caller_user)
      Logger.info(f"process_document link_document_response"
                  f"={link_document_response}")
  except Exception as e:
    Logger.error(
        f"process_document - Error for {document_path}:  {e}")
    err = traceback.format_exc().replace("\n", " ")
    Logger.error(err)
