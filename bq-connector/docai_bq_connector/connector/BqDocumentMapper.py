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

import json
import logging
from datetime import datetime
from typing import Sequence, List, Optional

from google.cloud.bigquery import SchemaField

from docai_bq_connector.connector.BqMetadataMapper import BqMetadataMapper
from docai_bq_connector.connector.ConversionError import ConversionError
from docai_bq_connector.doc_ai_processing.DocumentField import (
    DocumentRow,
    DocumentField,
)
from docai_bq_connector.doc_ai_processing.ProcessedDocument import ProcessedDocument
from docai_bq_connector.helper import find, get_bool_value, clean_number


class BqDocumentMapper:
    def __init__(
        self,
        document: ProcessedDocument,
        bq_schema: List[SchemaField],
        metadata_mapper: BqMetadataMapper,
        custom_fields: Optional[dict] = None,
        include_raw_entities: bool = True,
        include_error_fields: bool = True,
        continue_on_error: bool = False,
        parsing_methodology: str = "entities",
    ):
        self.processed_document = document
        self.bq_schema = bq_schema
        self.metadata_mapper = metadata_mapper
        self.custom_fields = custom_fields
        self.include_raw_entities = include_raw_entities
        self.include_error_fields = include_error_fields
        self.continue_on_error = continue_on_error
        self.parsing_methodology = parsing_methodology
        self.errors: List[ConversionError] = []
        self.fields = self._parse_document()
        self.dictionary = self._map_document_to_bigquery_schema(self.fields, bq_schema)

    def _parse_document(self) -> List[DocumentField]:
        row = self._parse_entities(self.processed_document.document.entities)
        return row.fields

    def _parse_entities(self, entities) -> DocumentRow:
        row = DocumentRow()
        for entity in entities:
            if len(entity.page_anchor.page_refs) != 1:
                continue
            if len(entity.properties) == 0:
                content = entity.mention_text
                value = (
                    content if content is not None and content.strip() != "" else None
                )
                if row.find_field_by_name(entity.type_) is not None:
                    self.errors.append(
                        ConversionError(
                            entity.type_,
                            value,
                            "Duplicate field definition",
                            None,
                            ConversionError.error_type_duplicate_field,
                            identifier=entity.id,
                        )
                    )
                    continue
                row.fields.append(
                    DocumentField(
                        entity.type_,
                        value,
                        entity.normalized_value,
                        entity.confidence,
                        entity.page_anchor.page_refs[0].page + 1,
                    )
                )
            else:
                parent_field = row.find_field_by_name(entity.type_)
                if parent_field is None:
                    parent_field = DocumentField(
                        entity.type_,
                        value,
                        entity.normalized_value,
                        entity.confidence,
                        entity.page_anchor.page_refs[0].page + 1,
                    )
                    row.fields.append(parent_field)
                parent_field.children.append(self._parse_entities(entity.properties))
        return row

    def to_bq_row(
        self,
        append_parsed_fields: bool = True,
        exclude_fields: Optional[List[str]] = None,
    ):
        row = {}
        if self.custom_fields is not None and len(self.custom_fields.keys()) > 0:
            row.update(self.custom_fields)

        if self.include_raw_entities is True:
            row["raw_entities"] = json.dumps(self.to_raw_entities())

        if append_parsed_fields is True:
            if exclude_fields is not None and len(exclude_fields) > 0:
                _dict = self.dictionary.copy()
                for field_name in exclude_fields:
                    if field_name in _dict:
                        error_val = _dict[field_name]
                        self.errors.append(
                            ConversionError(
                                field_name,
                                error_val,
                                "Excluding field due to BQ insert " "error",
                                None,
                                ConversionError.error_type_exclude_field,
                            )
                        )
                        del _dict[field_name]
                row.update(_dict)
            else:
                row.update(self.dictionary)

        if self.include_error_fields is True:
            row["has_errors"] = len(self.errors) != 0
            row["errors"] = self._error_list_dictionary()

        return row

    def process_insert_errors(self, errors: Sequence[dict]):
        error_records = []
        if len(errors) > 0:
            for err_list in errors:
                _errors = err_list.get("errors")
                if not _errors:
                    continue
                for err in _errors:
                    field_name = err.get("location")

                    # If a nested field has an error, exclude the top level field
                    if "." in field_name:
                        field_name = field_name[0 : field_name.split(".")[0].rfind("[")]

                    error_val = self.dictionary.get(field_name)
                    error_records.append(
                        ConversionError(
                            field_name,
                            error_val,
                            err.get("reason"),
                            err.get("message"),
                            ConversionError.error_type_bq_insert,
                        )
                    )
        self.errors.extend(error_records)
        return list(map(lambda x: x.key, error_records))

    def to_raw_entities(self):
        result = []
        fields = self.fields
        for field in fields:
            result.append(field.to_dictionary())
        return result

    def _map_document_to_bigquery_schema(
        self, fields: List[DocumentField], bq_schema: List[SchemaField]
    ):
        result: dict = {}
        for field in fields:
            field_name = field.to_bigquery_safe_name()
            if field.value is None:
                continue
            bq_field = find(
                lambda schema_field: schema_field.name == field_name, bq_schema
            )
            if bq_field is None:
                logging.warning(
                    "Parsed field '%s' not found in BigQuery schema. Field will be excluded from the "
                    "BigQuery payload",
                    field_name,
                )
                continue
            if bq_field.mode == "REPEATED":
                if len(bq_field.fields) == 0:
                    logging.warning("BQ field '%s' has no child fields", field_name)
                    continue
                if field_name not in result:
                    result[field_name] = []
                for child_row in field.children:
                    child_dict = self._map_document_to_bigquery_schema(
                        child_row.fields, bq_field.fields
                    )
                    if len(child_dict) > 0:
                        result[field_name].append(child_dict)
            else:
                _value = self._cast_type(field, bq_field.field_type)
                if isinstance(_value, ConversionError):
                    self.errors.append(_value)
                else:
                    result[field_name] = self._cast_type(field, bq_field.field_type)

        metadata_dict = self._map_document_metadata_to_bigquery_schema(bq_schema)
        result = result | metadata_dict
        return result

    def _map_document_metadata_to_bigquery_schema(self, bq_schema: List[SchemaField]):
        result: dict = {}
        mapped_metadata = self.metadata_mapper.map_metadata()
        for cur_metadata_mapping in mapped_metadata:
            col_name = cur_metadata_mapping["bq_column_name"]
            col_value = cur_metadata_mapping["bq_column_value"]
            if col_value is None:
                continue
            bq_field = find(
                lambda schema_field: schema_field.name == col_name, bq_schema
            )
            if bq_field is None:
                logging.warning(
                    "Parsed field '%s' not found in BigQuery schema. Field will be excluded from the "
                    "BigQuery payload",
                    col_name,
                )
                continue
            _value = self._cast_type(
                DocumentField(
                    name=col_name,
                    value=col_value,
                    normalized_value=col_value,
                    confidence=-1,
                    page_number=-1,
                ),
                bq_field.field_type,
            )
            if not isinstance(_value, ConversionError):
                result[col_name] = _value

        return result

    def _error_list_dictionary(self):
        return list(map(lambda x: x.to_dict(), self.errors))

    def _cast_type(self, field: DocumentField, bq_datatype):
        try:
            raw_value = (
                field.value.strip() if isinstance(field.value, str) else field.value
            )
            if self.parsing_methodology == "entities":
                if field.value is None:
                    return None
                if bq_datatype == "STRING":
                    return raw_value
                if bq_datatype == "BOOLEAN":
                    return get_bool_value(raw_value)
                if bq_datatype == "DATETIME":
                    if isinstance(field.value, datetime):
                        dt: datetime = field.value
                        return dt.isoformat()
                    return raw_value
                if bq_datatype in ("DECIMAL", "FLOAT", "NUMERIC"):
                    return float(clean_number(raw_value))
                if bq_datatype == "INTEGER":
                    return int(clean_number(raw_value))
                return raw_value
            elif self.parsing_methodology == "normalized_values":
                normalized_value = field.normalized_value
                if normalized_value is None:
                    return None
                if bq_datatype == "STRING":
                    return normalized_value.text
                if bq_datatype == "BOOLEAN":
                    return normalized_value.boolean_value
                if bq_datatype == "DATETIME":
                    return normalized_value.datetime_value
                if bq_datatype in ("DECIMAL", "FLOAT", "NUMERIC"):
                    return normalized_value.float_value
                if bq_datatype == "INTEGER":
                    return normalized_value.integer_value
                return raw_value
        except ValueError as ve:
            return ConversionError(
                field.name,
                field.value,
                f"ValueError: casting to {bq_datatype}",
                str(ve),
                ConversionError.error_type_conversion,
            )
