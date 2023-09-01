import argparse
import os
import sys
import time
from google.api_core.exceptions import NotFound
from google.cloud import storage
import json
from typing import List
from google.cloud import contentwarehouse_v1

sys.path.append(os.path.join(os.path.dirname(__file__), '../common/src'))
from common.utils.helper import is_date
from config import API_LOCATION, PROCESSOR_ID, \
  GCS_OUTPUT_BUCKET, DOCAI_PROJECT_NUMBER, DOCAI_WH_PROJECT_NUMBER, \
  FOLDER_SCHEMA_PATH, CALLER_USER

from common.utils.logging_handler import Logger
from common.utils.document_warehouse_utils import DocumentWarehouseUtils
from common.utils.docai_warehouse_helper import get_metadata_properties, \
  get_key_value_pairs
from common.utils.document_ai_utils import DocumentaiUtils
from common.utils import storage_utils, helper

assert PROCESSOR_ID, "PROCESSOR_ID not set"
assert GCS_OUTPUT_BUCKET, "GCS_OUTPUT_BUCKET not set"
assert DOCAI_PROJECT_NUMBER, "DOCAI_PROJECT_NUMBER not set"
assert DOCAI_WH_PROJECT_NUMBER, "DOCAI_WH_PROJECT_NUMBER not set"

dw_utils = DocumentWarehouseUtils(project_number=DOCAI_WH_PROJECT_NUMBER,
                                  api_location=API_LOCATION)
docai_utils = DocumentaiUtils(project_number=DOCAI_PROJECT_NUMBER,
                              api_location=API_LOCATION)

storage_client = storage.Client()
document_id_list = []
created_folders = []
files_to_parse = {}
processed_files = []
processed_dirs = set()
error_files = []
created_schemas = set()


def main(root_name: str):
  Logger.info(f"Batch load into DocumentAI WH using \n root_name={root_name}, "
              f"dir_uri={dir_uri}, overwrite={overwrite}, options={options}, flatten={flatten} \n"
              f"DOCAI_WH_PROJECT_NUMBER={DOCAI_WH_PROJECT_NUMBER}, "
              f"DOCAI_PROJECT_NUMBER={DOCAI_PROJECT_NUMBER}, "
              f"PROCESSOR_ID={PROCESSOR_ID}, \n"
              f"GCS_OUTPUT_BUCKET={GCS_OUTPUT_BUCKET}, "
              f"CALLER_USER={CALLER_USER}")
  initial_start_time = time.time()

  folder_schema_id = create_folder_schema(FOLDER_SCHEMA_PATH)

  bucket_name, prefix = helper.split_uri_2_bucket_prefix(dir_uri)
  if not prefix.endswith(".pdf") and prefix != "":
    prefix = prefix + "/"

  blobs = list(storage_client.list_blobs(bucket_name, prefix=prefix))

  if root_name is None:
    root_name = bucket_name

  for blob in blobs:
    filename = blob.name

    Logger.info(f'Handling {filename}')

    try:
      if filename.endswith(".pdf"):
        if flatten:
            dirs = [filename.replace("/", "__")]
        else:
            dirs = filename.split("/")
        if " " in dirs[:-1]:
          Logger.warning(f"Skipping {filename} since name contains space, currently this is not supported.")

        parent_id = create_folder(folder_schema_id, root_name, root_name)
        parent = dw_utils.get_document(parent_id, CALLER_USER)

        for d in dirs:
          reference_id = f"{parent.reference_id}__{d}".strip()
          if not d.endswith(".pdf"):
            processed_dirs.add(d)
            if reference_id not in created_folders:
              sub_folder_id = create_folder(folder_schema_id, d, reference_id)
              dw_utils.create_folder_link_document(
                  f"{dw_utils.location_path()}/documents/{parent_id}",
                  f"{dw_utils.location_path()}/documents/{sub_folder_id}",
                  CALLER_USER)
              created_folders.append(reference_id)

            parent = dw_utils.get_document(f"referenceId/{reference_id}",
                                           CALLER_USER)
            parent_id = parent.name.split("/")[-1]
          else:
            if document_exists(reference_id):
              if overwrite:
                delete_document(reference_id)
              else:
                Logger.info(
                  f"Skipping gs://{bucket_name}/{filename} since it already exists...")
                continue

            files_to_parse[f"gs://{bucket_name}/{filename}"] = (parent_id, reference_id)

            processed_files.append(filename)
    except Exception as ex:
      Logger.error(f"Exception {ex} while handling {filename}")
      error_files.append(filename)

  # Process All Documents in One batch
  docai_output_list = docai_utils.batch_extraction(PROCESSOR_ID,
                                                   list(files_to_parse.keys()),
                                                   GCS_OUTPUT_BUCKET)
  processor = docai_utils.get_processor(PROCESSOR_ID)
  document_schemas = get_document_schemas()

  for f_uri in docai_output_list:
    document_ai_output = docai_output_list[f_uri]
    if f_uri in files_to_parse:
      keys = get_key_value_pairs(document_ai_output)

      if schema_id:
        document_schema_id = schema_id
      else:
        if processor.display_name in document_schemas:
          document_schema_id = document_schemas[processor.display_name]
        else:
          schema_path = create_mapping_schema(processor.display_name, keys, options)
          document_schema_id = create_document_schema(schema_path)
          created_schemas.add(document_schema_id)

      (parent_id, reference_id) = files_to_parse[f_uri]
      schema = dw_utils.get_document_schema(document_schema_id)
      metadata_properties = get_metadata_properties(keys, schema)
      try:
        upload_document_gcs(f_uri, document_schema_id, parent_id, reference_id,
                            document_ai_output, metadata_properties)
      except Exception as ex:
        Logger.error(f"Failed to upload {f_uri} - {ex}")

  process_time = time.time() - initial_start_time
  time_elapsed = round(process_time)
  Logger.info(f"Job Completed in {str(round(time_elapsed / 60))} minute(s): \n"
              f"  - created document schemas={len(created_schemas)} \n"
              f"  - processed gcs files={len(processed_files)} \n"
              f"  - created dw documents={len(document_id_list)} \n"
              f"  - processed gcs directories={len(processed_dirs)} \n"
              f"  - created dw directories={len(created_folders)} \n")

  if len(error_files) != 0:
    Logger.info(
      f"Following files could not be handled (Document page number exceeding limit of 200 pages?")
    ",".join(error_files)


def get_type(value: str):
  if type(value) == bool:
    return "text_type_options" # bool Not Supported
  if is_date(value):
    return "date_time_type_options"
  # if is_valid_float(value):
  #   return "float_type_options"
  # if is_valid_int(value):
  #   return "integer_type_options"

  return "text_type_options"


def is_valid_float(string: str):
  try:
    float(string)
    return True
  except ValueError:
    return False


def is_valid_bool(string: str):
  return string.lower() in ["true", "false"]


def is_valid_int(string: str):
  return string.isdigit()


def create_mapping_schema(display_name, names, options=True):
  mapping_dic = {
      "display_name": display_name,
      "property_definitions": [],
      "document_is_folder": False,
      "description": "Auto-generated using batch Upload"
  }

  if options:
    for (name, value) in names:
      definition = {
          "name": name,
          "display_name": name,
          "is_repeatable": False,
          "is_filterable": True,
          "is_searchable": True,
          "is_metadata": True,
          "is_required": False,
      }

      v_type = get_type(value)
      if v_type:
        definition[v_type] = {}
      mapping_dic["property_definitions"].append(definition)

  file_path = os.path.join(os.path.dirname(__file__), "schema_files",
                           f'{display_name}.json')
  with open(file_path, 'w') as f:
    json.dump(mapping_dic, f, indent=2)

  return file_path


def document_exists(reference_id: str) -> bool:
  reference_path = f"referenceId/{reference_id}"
  try:
    dw_utils.get_document(reference_path, CALLER_USER)
    return True
  except NotFound as e:
    return False


def delete_document(reference_id: str):
  Logger.info(
      f"delete_document reference_id={reference_id}")
  reference_path = f"referenceId/{reference_id}"
  dw_utils.delete_document(document_id=reference_path,
                           caller_user_id=CALLER_USER)


def upload_document_gcs(file_uri: str, document_schema_id: str,
    folder_id: str, reference_id: str, document_ai_output,
    metadata_properties: List[contentwarehouse_v1.Property]):
  create_document_response = dw_utils.create_document(
      display_name=os.path.basename(file_uri),
      mime_type="application/pdf",
      document_schema_id=document_schema_id,
      raw_document_path=file_uri,
      docai_document=document_ai_output,
      caller_user_id=CALLER_USER,
      reference_id=reference_id,
      metadata_properties=metadata_properties
  )

  Logger.debug(
      f"create_document_response={create_document_response}")  # Verify that the properties have been set correctly

  if create_document_response is not None:
    document_id = create_document_response.document.name.split("/")[-1]
    document_id_list.append(document_id)

    dw_utils.link_document_to_folder(document_id=document_id,
                                     folder_document_id=folder_id,
                                     caller_user_id=CALLER_USER)
    Logger.info(f"Created document {file_uri} with reference_id={reference_id} inside folder_id={folder_id} and using schema_id={document_schema_id}")
    return document_id


def create_folder_schema(schema_path: str):
  folder_schema = storage_utils.read_file(schema_path, mode="r")
  display_name = json.loads(folder_schema).get("display_name")

  for ds in dw_utils.list_document_schemas():
    if ds.display_name == display_name and ds.document_is_folder:
      return ds.name.split("/")[-1]

  create_schema_response = dw_utils.create_document_schema(folder_schema)
  folder_schema_id = create_schema_response.name.split("/")[-1]

  Logger.info(f"folder_schema_id={folder_schema_id}")
  response = dw_utils.get_document_schema(schema_id=folder_schema_id)
  Logger.debug(f"response={response}")
  return folder_schema_id


def create_folder(folder_schema_id: str, display_name: str, reference_id: str):
  reference_path = f"referenceId/{reference_id}"
  try:
    document = dw_utils.get_document(reference_path, CALLER_USER)
    folder_id = document.name.split("/")[-1]
    return folder_id
  except NotFound as e:
    Logger.info(
        f" -------> Creating sub-folder [{display_name}] with reference_id=[{reference_id}]")
    create_folder_response = dw_utils.create_document(display_name=display_name,
                                                      document_schema_id=folder_schema_id,
                                                      caller_user_id=CALLER_USER,
                                                      reference_id=reference_id)
    if create_folder_response is not None:
      folder_id = create_folder_response.document.name.split("/")[-1]
      return folder_id


def get_document_schemas():
  schemas = {}
  for ds in dw_utils.list_document_schemas():
    if ds.display_name not in schemas:
      schemas[ds.display_name] = ds.name.split("/")[-1]
  return schemas


def create_document_schema(schema_path, overwrite_schema=False):
  document_schema = storage_utils.read_file(schema_path, mode="r")
  display_name = json.loads(document_schema).get("display_name")
  for ds in dw_utils.list_document_schemas():
    if ds.display_name == display_name and not ds.document_is_folder:
      document_schema_id = ds.name.split("/")[-1]
      if overwrite_schema:
        Logger.info(f"Removing {ds.display_name} with document_schema_id={document_schema_id}")
        dw_utils.delete_document_schema(document_schema_id)
      else:
        Logger.info(f"create_document_schema - Document schema with display_name = {display_name} already exists with schema_id = {document_schema_id}")
        return document_schema_id

  create_schema_response = dw_utils.create_document_schema(document_schema)
  document_schema_id = create_schema_response.name.split("/")[-1]
  Logger.info(
    f"create_document_schema - Created document schema with display_name = {display_name} and schema_id = {document_schema_id}")
  return document_schema_id


def get_args():
  # Read command line arguments
  args_parser = argparse.ArgumentParser(
      formatter_class=argparse.RawTextHelpFormatter,
      description="""
      Script to Batch load PDF data into the Document AI Warehouse.
      """,
      epilog="""
      Examples:

      python docai_wa_loaddocs.py -d=gs://my-folder [-n=UM_Guidelines]]
      """)

  args_parser.add_argument('-d', dest="dir_uri",
                           help="Path to gs directory uri, containing data with PDF documents to be loaded. All original structure of sub-folders will be preserved.")
  args_parser.add_argument('-s', dest="schema_id",
                           help="Optional existing schema_id.")
  args_parser.add_argument('-o', '--overwrite', dest="overwrite",
                           help="Overwrite files if already exist.",
                           action='store_true', default=False)
  args_parser.add_argument('--flatten', dest="flatten",
                           help="Flatten the directory structure.",
                           action='store_true', default=False)
  args_parser.add_argument('--options', dest="options",
                           help="Fill in document properties using schema options.",
                           action='store_true', default=False)
  args_parser.add_argument('-n', dest="root_name",
                           help="Name of the root folder inside DW where "
                                "documents will be loaded. When skipped, will use the same name of the folder being loaded from.")

  return args_parser


if __name__ == "__main__":
  parser = get_args()
  args = parser.parse_args()

  dir_uri = args.dir_uri
  root_name = args.root_name
  schema_id = args.schema_id
  overwrite = args.overwrite
  options = args.options
  flatten = args.flatten

  main(root_name)
