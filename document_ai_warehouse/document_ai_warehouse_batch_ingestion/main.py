import argparse
import json
import os
import time
from typing import List, Dict, Any, Set, Tuple, Optional
from config import API_LOCATION
from config import CALLER_USER
from config import DOCAI_PROJECT_NUMBER
from config import DOCAI_WH_PROJECT_NUMBER
from config import FOLDER_SCHEMA_PATH
from config import GCS_OUTPUT_BUCKET
from config import PROCESSOR_ID
from google.api_core.exceptions import NotFound
from google.cloud import contentwarehouse_v1
from google.cloud import storage
from common.utils import helper
from common.utils import storage_utils
from common.utils.docai_warehouse_helper import get_key_value_pairs
from common.utils.docai_warehouse_helper import get_metadata_properties
from common.utils.document_ai_utils import DocumentaiUtils
from common.utils.document_warehouse_utils import DocumentWarehouseUtils
from common.utils.helper import is_date
from common.utils.logging_handler import Logger

dw_utils = DocumentWarehouseUtils(
    project_number=DOCAI_WH_PROJECT_NUMBER, api_location=API_LOCATION
)
docai_utils = DocumentaiUtils(
    project_number=DOCAI_PROJECT_NUMBER, api_location=API_LOCATION
)

storage_client = storage.Client()


def get_schema(args: argparse.Namespace):
    file_uri = args.file_path
    schema_name = args.schema_name
    processor_id = args.processor_id
    if not processor_id:
        processor_id = PROCESSOR_ID

    Logger.info(
        f"Get document schema with: \nuri={file_uri}, processor_id={processor_id}, schema_name={schema_name} \n"
        f"GCS_OUTPUT_BUCKET={GCS_OUTPUT_BUCKET}, "
        f"CALLER_USER={CALLER_USER}"
    )

    assert processor_id, "processor_id is not set as PROCESSOR_ID env variable and " \
                         "is not provided as an input parameter (-p)"
    assert GCS_OUTPUT_BUCKET, "GCS_OUTPUT_BUCKET not set"
    assert DOCAI_PROJECT_NUMBER, "DOCAI_PROJECT_NUMBER not set"

    docai_output_list = docai_utils.batch_extraction(
        processor_id, [file_uri], GCS_OUTPUT_BUCKET
    )
    processor = docai_utils.get_processor(processor_id)

    for f in docai_output_list:
        document_ai_output = docai_output_list[f]
        keys = get_key_value_pairs(document_ai_output)

        if not schema_name:
            schema_name = processor.display_name
        schema_path = create_mapping_schema(schema_name, keys)
        print(f"Generated {schema_path} with document schema for {file_uri}")


def upload_schema(args: argparse.Namespace):
    schema_path = args.file_path
    overwrite = args.overwrite

    if not schema_path:
        Logger.error("Path to the schema file was not provided")
        return

    Logger.info(
        f"Upload document schema with: \nschema_path={schema_path}, overwrite={overwrite}"
    )
    create_document_schema(schema_path, overwrite)


def delete_schema(args: argparse.Namespace) -> None:
    schema_ids = args.schema_ids
    schema_names = args.schema_names

    if len(schema_ids) > 0:
        for schema_id in schema_ids:
            delete_schema_by_id(schema_id)
    if len(schema_names) > 0:
        for schema_name in schema_names:
            delete_schema_by_name(schema_name)


def batch_ingest(args: argparse.Namespace) -> None:
    dir_uri = args.dir_uri
    folder_name = args.root_name
    schema_id = args.schema_id
    schema_name = args.schema_name
    overwrite = args.overwrite
    options = args.options
    flatten = args.flatten
    processor_id = args.processor_id

    if not processor_id:
        processor_id = PROCESSOR_ID
    Logger.info(
        f"Batch load into DocumentAI WH using \n root_name={folder_name}, processor_id={processor_id},"
        f"dir_uri={dir_uri}, overwrite={overwrite}, options={options}, flatten={flatten} \n"
        f"DOCAI_WH_PROJECT_NUMBER={DOCAI_WH_PROJECT_NUMBER}, "
        f"DOCAI_PROJECT_NUMBER={DOCAI_PROJECT_NUMBER}, "
        f"GCS_OUTPUT_BUCKET={GCS_OUTPUT_BUCKET}, "
        f"CALLER_USER={CALLER_USER}"
    )

    assert processor_id, "processor_id is not set as PROCESSOR_ID env variable and " \
                         "is not provided as an input parameter (-p)"
    assert GCS_OUTPUT_BUCKET, "GCS_OUTPUT_BUCKET not set"
    assert DOCAI_PROJECT_NUMBER, "DOCAI_PROJECT_NUMBER not set"
    assert DOCAI_WH_PROJECT_NUMBER, "DOCAI_WH_PROJECT_NUMBER not set"

    initial_start_time = time.time()

    created_folders, files_to_parse, processed_files, processed_dirs, error_files = \
        prepare_file_structure(dir_uri, folder_name, overwrite, flatten)

    created_schemas, document_id_list = proces_documents(files_to_parse, schema_id, schema_name, processor_id, options)

    process_time = time.time() - initial_start_time
    time_elapsed = round(process_time)
    document_schema_str = ""
    if len(created_schemas) > 0:
        document_schema_str = (
            f"  - created document schema with id {','.join(list(created_schemas))}"
        )
    Logger.info(
        f"Job Completed in {str(round(time_elapsed / 60))} minute(s): \n"
        f"{document_schema_str}  \n"
        f"  - processed gcs files={len(processed_files)} \n"
        f"  - created dw documents={len(document_id_list)} \n"
        f"  - processed gcs directories={len(processed_dirs)} \n"
        f"  - created dw directories={len(created_folders)} \n"
    )
    if len(error_files) != 0:
        Logger.info(
            f"Following files could not be handled (Document page number exceeding limit of 200 pages? "
            f"{','.join(error_files)}"
        )


FUNCTION_MAP = {'batch_ingest': batch_ingest,
                'get_schema': get_schema,
                'upload_schema': upload_schema,
                'delete_schema': delete_schema,
                }


def main():
    parser = get_args()
    args = parser.parse_args()
    func = FUNCTION_MAP[args.command]
    func(args)


def get_args():
    # Read command line arguments
    args_parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description="""
      Script with multiple commands options to batch_ingest documents, generate schema,
      upload schema or delete schema using Document AI Warehouse.
      """,
        epilog="""
      Examples:

      Batch ingestion of files inside GCS directory:
      > python main.py batch_ingest -d=gs://my-folder -p PROCESSOR_ID [-n=UM_Guidelines] [-sn=schema_name] [--overwrite]

      Generate document schema based on the Document AI output:
      > python main.py get_schema -f=gs://my-folder/my-form.pdf -p PROCESSOR_ID [-sn=schema_name]

      Upload document schema into Document AI WH:
      > python main.py upload_schema -f=gs://my-folder/schema_name.json [-o]

      Delete document schema from Document AI WH:
      > python main.py delete_schema -ss=schema_id1 -ss=schena_id2 -sns=schema_name1 -sns=schema_name2
      """,
    )

    args_parser.add_argument('command', choices=FUNCTION_MAP.keys())
    args_parser.add_argument(
        "-d",
        dest="dir_uri",
        help="Path to gs directory uri, containing data with PDF documents to be loaded. "
             "All original structure of sub-folders will be preserved.",
    )
    args_parser.add_argument(
        "-s", dest="schema_id", help="Optional existing schema_id."
    )
    args_parser.add_argument(
        "-p", dest="processor_id", help="Processor_ID."
    )
    args_parser.add_argument(
        "-sn",
        dest="schema_name",
        help="Optional name of the schema to be created (should not exist).",
    )
    args_parser.add_argument(
        "-o",
        "--overwrite",
        dest="overwrite",
        help="Overwrite files/schema if already exist.",
        action="store_true",
        default=False,
    )
    args_parser.add_argument(
        "-f",
        dest="file_path",
        help="Path to file.",
    )
    args_parser.add_argument(
        "--flatten",
        dest="flatten",
        help="Flatten the directory structure.",
        action="store_true",
        default=False,
    )
    args_parser.add_argument(
        "--options",
        dest="options",
        help=" When set (by default), will automatically fill in document properties using schema options.",
        action="store_true",
        default=True,
    )
    args_parser.add_argument(
        "-n",
        dest="root_name",
        help="Name of the root folder inside DW for batch ingestion."
             " When skipped, will use the same name of the folder being loaded from.",
    )
    args_parser.add_argument(
        "-sns",
        dest="schema_names",
        action="append",
        default=[],
        help="Schema display_name to be deleted.",
    )
    args_parser.add_argument(
        "-ss",
        dest="schema_ids",
        action="append",
        default=[],
        help="Schema_ids to be deleted.",
    )
    return args_parser


def proces_documents(
        files_to_parse: Dict[str, Any],
        schema_id: str,
        schema_name: str,
        processor_id: str,
        options: bool
) -> Tuple[Set[str], List[str]]:
    created_schemas: Set[str] = set()
    document_id_list: List[str] = []

    if len(files_to_parse) == 0:
        return created_schemas, document_id_list

    docai_output_list = docai_utils.batch_extraction(
        processor_id, list(files_to_parse.keys()), GCS_OUTPUT_BUCKET
    )
    processor = docai_utils.get_processor(processor_id)
    document_schemas = get_document_schemas()
    document_schema_id = None
    if not schema_name:
        schema_name = processor.display_name
    for f_uri in docai_output_list:
        document_ai_output = docai_output_list[f_uri]
        if f_uri in files_to_parse:
            keys = get_key_value_pairs(document_ai_output)
            create_new_schema = False

            if schema_id:
                document_schema_id = schema_id
            else:
                if schema_name in document_schemas:
                    document_schema_id = document_schemas[schema_name]
                    schema = dw_utils.get_document_schema(document_schema_id)
                    if (
                        schema
                        and len(keys) != 0
                        and len(schema.property_definitions) == 0
                        and options
                    ):
                        create_new_schema = True
                else:
                    create_new_schema = True

            if create_new_schema:
                schema_path = create_mapping_schema(schema_name, keys, options)
                new_schema_id = create_document_schema(schema_path, True)
                if document_schema_id != new_schema_id:
                    created_schemas.add(new_schema_id)
                    document_schemas[schema_name] = new_schema_id
                    document_schema_id = new_schema_id

            (parent_id, reference_id) = files_to_parse[f_uri]
            schema = dw_utils.get_document_schema(document_schema_id)

            metadata_properties = get_metadata_properties(keys, schema)

            if document_schema_id:
                try:
                    document_id = upload_document_gcs(
                        f_uri,
                        document_schema_id,
                        parent_id,
                        reference_id,
                        document_ai_output,
                        metadata_properties,
                    )
                    if document_id:
                        document_id_list.append(document_id)
                except Exception as ex:
                    Logger.error(f"Failed to upload {f_uri} - {ex}")

    return created_schemas, document_id_list


def prepare_file_structure(
    dir_uri: str,
    folder_name: str,
    overwrite: bool,
    flatten: bool,
):

    created_folders = []
    files_to_parse = {}
    processed_files = []
    processed_dirs = set()
    error_files = []

    folder_schema_id = create_folder_schema(FOLDER_SCHEMA_PATH)

    bucket_name, prefix = helper.split_uri_2_bucket_prefix(dir_uri)
    if not prefix.endswith(".pdf") and prefix != "":
        prefix = prefix + "/"

    blobs = list(storage_client.list_blobs(bucket_name, prefix=prefix))
    if folder_name is None:
        folder_name = bucket_name

    for blob in blobs:
        filename = blob.name
        Logger.info(f"Handling {filename}")

        try:
            if filename.endswith(".pdf"):
                if flatten:
                    dirs = [filename.replace("/", "__")]
                else:
                    dirs = filename.split("/")
                if " " in dirs[:-1]:
                    Logger.warning(
                        f"Skipping {filename} since name contains space, currently this is not supported."
                    )

                parent_id = create_folder(folder_schema_id, folder_name, folder_name)
                parent = dw_utils.get_document(parent_id, CALLER_USER)

                for d in dirs:
                    reference_id = f"{parent.reference_id}__{d}".strip()
                    if not d.endswith(".pdf"):
                        processed_dirs.add(d)
                        if reference_id not in created_folders:
                            create_folder(folder_schema_id, d, reference_id)
                            created_folders.append(reference_id)

                        parent = dw_utils.get_document(
                            f"referenceId/{reference_id}", CALLER_USER
                        )
                        parent_id = parent.name.split("/")[-1]
                    else:
                        if document_exists(reference_id):
                            if overwrite:
                                delete_document(reference_id)
                            else:
                                Logger.info(
                                    f"Skipping gs://{bucket_name}/{filename} since it already exists..."
                                )
                                continue

                        files_to_parse[f"gs://{bucket_name}/{filename}"] = (
                            parent_id,
                            reference_id,
                        )

                        processed_files.append(filename)
        except Exception as ex:
            Logger.error(f"Exception {ex} while handling {filename}")
            error_files.append(filename)

    return created_folders, files_to_parse, processed_files, processed_dirs, error_files


def get_type(value: str) -> str:
    if type(value) == bool or str(value) == "":
        return "text_type_options"  # bool Not Supported
    if is_date(value):
        return "date_time_type_options"
    if is_valid_int(value):
        return "integer_type_options"
    if is_valid_float(value):
        return "float_type_options"

    return "text_type_options"


def is_valid_float(string: str) -> bool:
    try:
        float(string)
        return True
    except ValueError:
        return False


def is_valid_bool(string: str) -> bool:
    return string.lower() in ["true", "false"]


def is_valid_int(string: str) -> bool:
    return string.isdigit()


def create_mapping_schema(display_name: str, names, options: bool = True) -> str:
    properties: List[Dict[str, Any]] = []
    mapping_dic = {
        "display_name": display_name,
        "property_definitions": [],
        "document_is_folder": False,
        "description": "Auto-generated using batch upload",
    }

    if options:
        for name, value in names:
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
            properties.append(definition)

        mapping_dic["property_definitions"] = properties

    file_path = os.path.join(
        os.path.dirname(__file__), "schema_files", f"{display_name}.json"
    )
    with open(file_path, "w") as f:
        json.dump(mapping_dic, f, indent=2)

    return file_path


def document_exists(reference_id: str) -> bool:
    reference_path = f"referenceId/{reference_id}"
    try:
        dw_utils.get_document(reference_path, CALLER_USER)
        return True
    except NotFound:
        return False


def delete_document(reference_id: str) -> None:
    Logger.info(f"delete_document reference_id={reference_id}")
    reference_path = f"referenceId/{reference_id}"
    dw_utils.delete_document(document_id=reference_path, caller_user_id=CALLER_USER)


def upload_document_gcs(
    file_uri: str,
    document_schema_id: str,
    folder_id: str,
    reference_id: str,
    document_ai_output,
    metadata_properties: List[contentwarehouse_v1.Property],
) -> Optional[str]:
    create_document_response = dw_utils.create_document(
        display_name=os.path.basename(file_uri),
        mime_type="application/pdf",
        document_schema_id=document_schema_id,
        raw_document_path=file_uri,
        docai_document=document_ai_output,
        caller_user_id=CALLER_USER,
        reference_id=reference_id,
        metadata_properties=metadata_properties,
    )

    Logger.debug(
        f"create_document_response={create_document_response}"
    )  # Verify that the properties have been set correctly

    if create_document_response:
        document_id = create_document_response.document.name.split("/")[-1]
        dw_utils.link_document_to_folder(
            document_id=document_id,
            folder_document_id=folder_id,
            caller_user_id=CALLER_USER,
        )
        Logger.info(
            f"Created document {file_uri} with reference_id={reference_id} inside folder_id={folder_id} "
            f"and using schema_id={document_schema_id}"
        )
        return document_id

    return None


def create_folder_schema(schema_path: str) -> str:
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


def create_folder(folder_schema_id: str, display_name: str, reference_id: str) -> Optional[str]:
    reference_path = f"referenceId/{reference_id}"
    try:
        document = dw_utils.get_document(reference_path, CALLER_USER)
        folder_id = document.name.split("/")[-1]
        return folder_id
    except NotFound:
        Logger.info(
            f" -------> Creating sub-folder [{display_name}] with reference_id=[{reference_id}]"
        )
        create_folder_response = dw_utils.create_document(
            display_name=display_name,
            document_schema_id=folder_schema_id,
            caller_user_id=CALLER_USER,
            reference_id=reference_id,
        )
        if create_folder_response is not None:
            folder_id = create_folder_response.document.name.split("/")[-1]
            return folder_id
    return None


def get_document_schemas() -> Dict[str, Any]:
    schemas = {}
    for ds in dw_utils.list_document_schemas():
        if ds.display_name not in schemas:
            schemas[ds.display_name] = ds.name.split("/")[-1]
    return schemas


def create_document_schema(schema_path: str, overwrite_schema: bool = False) -> str:
    document_schema = storage_utils.read_file(schema_path, mode="r")
    display_name = json.loads(document_schema).get("display_name")
    for ds in dw_utils.list_document_schemas():
        if ds.display_name == display_name and not ds.document_is_folder:
            document_schema_id = ds.name.split("/")[-1]
            if overwrite_schema:
                try:
                    Logger.info(
                        f"Removing {ds.display_name} with document_schema_id={document_schema_id}"
                    )
                    dw_utils.delete_document_schema(document_schema_id)
                except Exception as ex:
                    Logger.warning(f"Could not replace schema due to error {ex}")
                    return document_schema_id
            else:
                Logger.info(
                    f"create_document_schema - Document schema with display_name = {display_name} already "
                    f"exists with schema_id = {document_schema_id}"
                )
                return document_schema_id

    create_schema_response = dw_utils.create_document_schema(document_schema)
    document_schema_id = create_schema_response.name.split("/")[-1]
    Logger.info(
        f"create_document_schema - Created document schema with display_name = {display_name} "
        f"and schema_id = {document_schema_id}"
    )
    return document_schema_id


def delete_schema_by_id(schema_id: str) -> None:
    try:
        Logger.info(f"Removing schema with schema_id={schema_id}")
        dw_utils.delete_document_schema(schema_id)
    except Exception as ex:
        Logger.warning(f"Could not replace schema due to error {ex}")


def delete_schema_by_name(display_name: str) -> None:
    Logger.info(f"Deleting schema with display_name={display_name}")
    for ds in dw_utils.list_document_schemas():
        if ds.display_name == display_name and not ds.document_is_folder:
            document_schema_id = ds.name.split("/")[-1]
            try:
                Logger.info(
                    f"Removing {ds.display_name} with document_schema_id={document_schema_id}"
                )
                dw_utils.delete_document_schema(document_schema_id)
            except Exception as ex:
                Logger.warning(f"Could not delete schema due to error {ex}")

            else:
                Logger.info(
                    f"Schema with display_name={display_name} and schema_id={document_schema_id}  "
                    f"has been successfully deleted "
                )


if __name__ == "__main__":
    main()
