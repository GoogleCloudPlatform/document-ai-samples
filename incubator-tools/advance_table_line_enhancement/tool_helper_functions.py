# Copyright 2023 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""This module contains helper functions for Advance Table Parsing Tool"""
import math
import re
import time
from collections import defaultdict
from io import BytesIO
from typing import DefaultDict, Dict, List, MutableSequence, Tuple, Union

import traceback
import numpy as np
import pandas as pd
import PyPDF2
from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import InternalServerError, RetryError
from google.cloud import documentai, storage
from google.longrunning import operations_pb2
from google.longrunning.operations_pb2 import GetOperationRequest
from PIL import Image as PilImage
from PIL import ImageDraw


def batch_process_documents(
    project_id: str,
    location: str,
    processor_id: str,
    gcs_input_uri: str,
    gcs_output_bucket: str,
    gcs_output_uri_prefix: str,
    field_mask: Union[str, None] = None,
    timeout: int = 5000,
    processor_version_id: Union[str, None] = None,
) -> Tuple[documentai.BatchProcessMetadata, str]:
    """
    Performs batch operation on input gcs folder
    Args:
        project_id (str): Google Cloud project ID.
        location (str): Location of the processor.
        processor_id (str): ID of the Document AI processor.
        gcs_input_uri (str): Cloud Storage URI for the input GCS folder.
        gcs_output_bucket (str): Google Cloud Storage bucket for output.
        gcs_output_uri_prefix (str): Output GCS URI prefix.
        field_mask (Union[str, None]): Field mask for output. Defaults to None.
        timeout (int): Timeout for the operation. Defaults to 5000.
        processor_version_id (Union[str, None]): Processor version ID. Defaults to None.
    Returns:
        Tuple[documentai.BatchProcessMetadata, str]: Tuple containing metadata and operation ID.
    """

    # You must set the api_endpoint if you use a location other than 'us'.
    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    # gcs_input_uri = "gs://bucket/direcory_prefix"
    print("gcs_input_uri", gcs_input_uri)
    gcs_prefix = documentai.GcsPrefix(gcs_uri_prefix=f"{gcs_input_uri}/")
    input_config = documentai.BatchDocumentsInputConfig(gcs_prefix=gcs_prefix)
    # Cloud Storage URI for the Output Directory
    # This must end with a trailing forward slash `/`
    destination_uri = f"{gcs_output_bucket}/{gcs_output_uri_prefix}/"
    print("gcs_output_uri", destination_uri)
    gcs_output_config = documentai.DocumentOutputConfig.GcsOutputConfig(
        gcs_uri=destination_uri, field_mask=field_mask
    )
    # Where to write results
    output_config = documentai.DocumentOutputConfig(gcs_output_config=gcs_output_config)
    if processor_version_id:
        # The full resource name of the processor version, e.g.:
        # base_url = "projects/{project_id}/locations/{location}/processors/{processor_id}/"
        # url = base_url + "processorVersions/{processor_version_id}"
        name = client.processor_version_path(
            project_id, location, processor_id, processor_version_id
        )
    else:
        # The full resource name of the processor, e.g.:
        # projects/{project_id}/locations/{location}/processors/{processor_id}
        name = client.processor_path(project_id, location, processor_id)
    request = documentai.BatchProcessRequest(
        name=name,
        input_documents=input_config,
        document_output_config=output_config,
    )
    # BatchProcess returns a Long Running Operation (LRO)
    operation = client.batch_process_documents(request)
    # Continually polls the operation until it is complete.
    # This could take some time for larger files
    # Format: projects/PROJECT_NUMBER/locations/LOCATION/operations/OPERATION_ID

    try:
        print(f"Waiting for operation {operation.operation.name} to complete...")
        operation.result(timeout=timeout)
    # Catch exception when operation doesn't finish before timeout
    except (RetryError, InternalServerError) as e:
        print(e.message)

    # NOTE: Can also use callbacks for asynchronous processing
    #
    # def my_callback(future):
    #   result = future.result()
    #
    # operation.add_done_callback(my_callback)

    # Once the operation is complete,
    # get output document information from operation metadata
    metadata = documentai.BatchProcessMetadata(operation.metadata)
    if metadata.state != documentai.BatchProcessMetadata.State.SUCCEEDED:
        raise ValueError(f"Batch Process Failed: {metadata.state_message}")
    return metadata, operation.operation.name.split("/")[-1]


def read_json_output(
    output_bucket: str, output_prefix: str, hitl: bool = False
) -> Dict[str, documentai.Document]:
    """
    Read the processor json output stored in the GCS bucket.
    Args:
        output_bucket (str): Google Cloud Storage bucket for the output.
        output_prefix (str): Output GCS URI prefix.
        hitl (bool): Flag indicating whether Human in the Loop (HITL) is enabled. Defaults to False.
    Returns:
        Dict[str, documentai.Document]: Dictionary containing Document objects.
    """

    storage_client = storage.Client()
    documents = {}
    # Get List of Document Objects from the Output Bucket
    output_blobs = storage_client.list_blobs(output_bucket, prefix=output_prefix)
    # Document AI may output multiple JSON files per source file
    # For current pipeline, assumption is we will have single JSON file
    for blob in output_blobs:
        # Document AI should only output JSON files to GCS
        if ".json" not in blob.name:
            print(
                f"Skipping non-supported file: {blob.name} - Mimetype: {blob.content_type}"
            )
            continue
        # Download JSON File as bytes object and convert to Document Object
        print(f"Fetching {blob.name}")
        document = documentai.Document.from_json(
            blob.download_as_bytes(), ignore_unknown_fields=True
        )
        if hitl:
            documents[blob.name.split("/")[-2]] = document
        else:
            documents[blob.name.split("/")[-1][:-7]] = document
    return documents


def get_processor_metadata(
    cde_metadatap: documentai.Document, fp: bool = False
) -> Dict[str, Union[str, Dict[str, str]]]:
    """
    Parse the processor LRO operation metadata.
    Args:
        cde_metadatap (documentai.Document): Document containing processor LRO operation metadata.
        fp (bool): Flag indicating whether to include file paths. Defaults to False.

    Returns:
        Dict[str, Union[str, Dict[str, str]]]: Mapping of file names to output details.
    """

    input_output_map: Dict[str, Union[str, Dict[str, str]]] = {}
    for process in cde_metadatap.individual_process_statuses:
        filen = process.input_gcs_source.split("/")[-1]
        output = "/".join(process.output_gcs_destination.split("/")[3:])
        if fp:
            input_output_map[filen] = output
        else:
            hitl = process.human_review_status.human_review_operation.split("/")[-1]
            input_output_map[filen] = {"cde": output, "hitl": hitl}
    return input_output_map


def layout_to_text(layout: documentai.Document.Page.Layout, text: str) -> str:
    """
    Document AI identifies text in different parts of the document by their
    offsets in the entirety of the document's text. This function converts
    offsets to a string.
    Args:
        layout (documentai.Document.Page.Layout): Layout information for a page.
        text (str): The entire text content of the document.
    Returns:
        str: Concatenated text corresponding to the specified layout.
    """

    response = ""
    # If a text segment spans several lines, it will
    # be stored in different text segments.
    for segment in layout.text_anchor.text_segments:
        start_index = int(segment.start_index)
        end_index = int(segment.end_index)
        response += text[start_index:end_index]
    return response


def get_matched_field(block_text: str, pattern: str = "([0-9]+)") -> str:
    """
    Search particular pattern in cell values.
    Args:
        block_text (str): The text content of the block.
        pattern (str): Regular expression pattern to search in the block text.
        Defaults to "([0-9]+)".
    Returns:
        str: Matched field based on the specified pattern.
    """

    m = re.search(pattern, block_text)
    t = ""
    if m:
        for seq, grp in enumerate(m.groups()):
            if grp:
                if seq == 0:
                    t = m.group(seq + 1)
                else:
                    t += " " + m.group(seq + 1)
        return t.strip()
    return t


def get_processed_map(
    row_map: Dict[int, Dict[str, List[int]]], offset: int
) -> Dict[int, Dict[str, List[int]]]:
    """
    Adjust the headers boundaries.
    Args:
        row_map (Dict[int, Dict[str, List[int]]]): Mapping of rows to headers with boundaries.
        offset (int): Offset value for adjusting header boundaries.
    Returns:
        Dict[int, Dict[str, List[int]]]: Adjusted header boundaries in the processed map.
    """

    processed_map_ = {}
    for k, v in row_map.items():
        processed_map = {
            i: [round(j[0] / 10) - offset, round(j[1] / 10) + offset]
            for i, j in v.items()
            if i not in ["DNSH", "SCC"]
        }
        a, b = processed_map["taxonomy_disclosure"]
        processed_map["taxonomy_disclosure"] = [a, b + 2]
        processed_map_[k] = processed_map
    return processed_map_


def get_coordinates_map(
    document: documentai.Document,
) -> Tuple[
    Dict[int, List[List[int]]],
    Dict[int, List[int]],
    Dict[int, Dict[str, List[int]]],
    Dict[int, List[int]],
]:
    """
    Get headers and rows coordinates.
    Args:
        document(documentai.Document): Document containing information.
    Returns:
        Tuple
    """

    # row_keywords = {"taxonomy","sum","economic","taxonomy-eligible","taxonomy-non-eligible"}
    x_coordinates_ = {}
    y_coord_ = {}
    row_map_ = {}
    max_ycd_ = {}
    for pn, _ in enumerate(document.pages):
        row_coords = []
        x_coordinates = []
        y_coord = []
        row_map = {}
        max_ycd = []
        dimension = document.pages[pn].dimension
        width, height = dimension.width, dimension.height
        # capture min col y of table
        ycd_min = math.inf
        # capture min row y of table
        for entity in document.entities:
            pno = entity.page_anchor.page_refs[0].page
            if pno != pn:
                continue
            if entity.type_ in ["DNSH", "SCC"]:
                continue
            ycd = -1
            xx = []
            for coord in entity.page_anchor.page_refs[
                0
            ].bounding_poly.normalized_vertices:
                x = round(coord.x * width)
                y = round(coord.y * height)
                if entity.type_ == "activity":
                    ycd = max(ycd, y)
                elif entity.type_ == "taxonomy_disclosure":
                    row_coords.append(x)
                    y = round(coord.y * height)
                    ycd = max(ycd, y)
                    y_coord.append(y)
                elif x not in xx:
                    xx.append(x)
                    ycd_min = min(ycd_min, y)
            if ycd != -1:
                max_ycd.append(ycd)
            if xx:
                # sort the x1,x2 coordinates before storing
                xx.sort()
                x_coordinates.append(xx)
                row_map[entity.type_] = xx
        if row_coords:
            row_min_max = [min(row_coords), max(row_coords)]
            x_coordinates.append(row_min_max)
            row_map["taxonomy_disclosure"] = row_min_max

        # store the min col y of table
        if ycd_min != math.inf:
            max_ycd.append(math.ceil(ycd_min))
        x_coordinates.sort(key=lambda x: x[0])
        x_coordinates_[pn] = x_coordinates
        y_coord.sort()
        y_coord_[pn] = y_coord
        max_ycd.sort()
        max_ycd_[pn] = max_ycd
        row_map_[pn] = row_map
    return x_coordinates_, y_coord_, row_map_, max_ycd_


def get_operation(location: str, operation_name: str) -> operations_pb2.Operation:
    """
    Gets Long Running Operation details.
    Args:
        location (str): Location of the operation.
        operation_name (str): Name of the operation.
    Returns:
        operations_pb2.Operation: Long Running Operation details.
    """

    # You must set the `api_endpoint` if you use a location other than "us".
    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    request = GetOperationRequest(name=operation_name)
    operation = client.get_operation(request=request)
    return operation


def poll_hitl_operations(
    project_num: str, location: str, metadata: Dict[str, Dict[str, str]]
) -> None:
    """
    Poll Long Running Operation to check status.
    Args:
        project_num (str): Project number.
        location (str): Location of the operation.
        metadata (Dict[str, Dict[str, str]]): Metadata containing HITL information.
    """
    # use callbacks for asynchronous processing
    #     def my_callback(future):
    #         result = future.result()
    operations = []
    for v in metadata.values():
        operation_id = v.get("hitl", None)
        if operation_id:
            operation_name = (
                f"projects/{project_num}/locations/{location}/operations/{operation_id}"
            )
            operations.append(operation_name)
    num_operations = len(operations)
    print(f"Successfully scheduled {num_operations} HITL operations.")
    while operations:
        operations = [
            operation
            for operation in operations
            if not get_operation(location, operation).done
        ]
        if not operations:
            break
        print(f"Still waiting for {len(operations)} HITL operations to complete")
        time.sleep(100)
    print(f"Finished waiting for all {num_operations} HITL operations.")


def get_table_data_(
    rows: MutableSequence[documentai.Document.Page.Table.TableRow], text: str
) -> List[List[str]]:
    """
    Get Text data from table rows
    Args:
        rows (MutableSequence[documentai.Document.Page.Table.TableRow]): List of table rows.
        text (str): Full text of the document.

    Returns:
        List[List[str]]: List of lists containing the text data from table rows.
    """

    all_values = []
    for row in rows:
        current_row_values = []
        for cell in row.cells:
            current_row_values.append(
                text_anchor_to_text(cell.layout.text_anchor, text)
            )
        all_values.append(current_row_values)
    return all_values


def text_anchor_to_text(text_anchor: documentai.Document.TextAnchor, text: str) -> str:
    """
    Document AI identifies table data by their offsets in the entirety of the
    document's text. This function converts offsets to a string.
    Args:
        text_anchor (object): It contains information about textanchor offsets.
        text (str): Full text of the document.
    Returns:
        str: Converted text based on the specified offsets.
    """

    response = ""
    # If a text segment spans several lines, it will
    # be stored in different text segments.
    for segment in text_anchor.text_segments:
        start_index = int(segment.start_index)
        end_index = int(segment.end_index)
        response += text[start_index:end_index]
    return response.strip().replace("\n", " ")


def parse_document_tables(output_bucket, output_prefix, output_csv_prefix):
    """
    Parse the Form Parser output to extract tables.
    Args:
        output_bucket (str): Name of the GCS bucket where the output is stored.
        output_prefix (str): Prefix for the output files.
        output_csv_prefix (str): Prefix for the CSV files to be created.
    """
    # storage_client = storage.Client()
    # bucket = storage_client.bucket(output_bucket)
    # Read the document
    doc_obj_dict = read_json_output(
        output_bucket=output_bucket, output_prefix=output_prefix
    )
    for file_key, document in doc_obj_dict.items():
        for _, page in enumerate(document.pages):
            header_row_values: List[List[str]] = []
            body_row_values: List[List[str]] = []
            for index, table in enumerate(page.tables):
                header_row_values = get_table_data_(table.header_rows, document.text)
                body_row_values = get_table_data_(table.body_rows, document.text)
                # Create a Pandas DataFrame to print the values in tabular format.
                df = pd.DataFrame(
                    data=body_row_values,
                    columns=pd.MultiIndex.from_arrays(header_row_values),
                )
                # Save each table as a CSV file in the GCS bucket
                output_filename = (
                    f"{output_csv_prefix}/{file_key}/pg{page.page_number}_tb{index}.csv"
                )
                df.to_csv(f"gs://{output_bucket}/{output_filename}", index=False)


def get_hitl_state(hitl_status_response: operations_pb2.Operation) -> Tuple[bool, str]:
    """
    Returns the HITL state and gcs output path if the document is reviewed.
    Args:
        hitl_status_response (operations_pb2.Operation): HITL status response.
    Returns:
        Tuple[bool, str]: Tuple containing a boolean indicating whether the document
        is reviewed (True if reviewed, False otherwise) and the GCS output path.
    """

    hitl_response = documentai.ReviewDocumentResponse.deserialize(
        hitl_status_response.response.value
    )
    hitl_status = hitl_response.state.name
    hitl_destination = hitl_response.gcs_destination
    if hitl_status == "REJECTED":
        return False, ""
    return True, hitl_destination


def parse_and_split_pages(
    individual_process_statuses: MutableSequence[
        documentai.BatchProcessMetadata.IndividualProcessStatus
    ],
    output_bucket_name: str,
    output_folder: str,
    label: str,
    location: str,
) -> None:
    """
    Function takes the CDS output, splits it, and produces PDFs containing taxonomy tables,
    then stores them in the specified output directory.
    Args:
        individual_process_statuses (MutableSequence): List of individual process statuses.
        output_bucket_name (str): Output bucket name.
        output_folder (str): Output folder.
        label (str): Taxonomy label.
        location (str): Location.
    Returns:
        None
    """

    client = storage.Client()
    for status in individual_process_statuses:
        source_bucket_name, source_blob_path = status.input_gcs_source.replace(
            "gs://", ""
        ).split("/", 1)
        operation_id = status.human_review_status.human_review_operation.split("/")[-1]
        if operation_id:
            print("operation_id:", operation_id)
            hitl_status_response = get_operation(
                location, status.human_review_status.human_review_operation
            )
            state, destination = get_hitl_state(hitl_status_response)
            if state:
                dest_bucket_name, dest_file_name = destination.replace(
                    "gs://", ""
                ).split("/", 1)
                dest_blob_path = "/".join(dest_file_name.split("/")[:-1])
            else:
                continue
        else:
            dest_bucket_name, dest_blob_path = status.output_gcs_destination.replace(
                "gs://", ""
            ).split("/", 1)
            dest_file_name = f"{dest_blob_path}/output-document.json"
        source_pdf_name = source_blob_path.split("/")[-1].replace(".pdf", "")
        dest_blob_name = f"{dest_blob_path}/{source_pdf_name}.json"
        # Copy the source blob to the new location with a new name
        # For debugging purpose
        client.bucket(dest_bucket_name).copy_blob(
            client.bucket(dest_bucket_name).blob(dest_file_name),
            client.bucket(dest_bucket_name),
            dest_blob_name,
        )
        # Read JSON data from GCS
        json_blob = client.bucket(dest_bucket_name).blob(dest_blob_name)
        json_data = documentai.Document.from_json(
            json_blob.download_as_text(), ignore_unknown_fields=True
        )
        entities = json_data.entities
        taxonomy_page_no = []
        for entity in entities:
            if entity.type_ == label:
                taxonomy_page_anchor = entity.page_anchor.page_refs
                for ta_pa in taxonomy_page_anchor:
                    page_number = ta_pa.page
                    taxonomy_page_no.append(page_number)
        # Read PDF from GCS
        pdf_blob = client.bucket(source_bucket_name).blob(source_blob_path)
        pdf_data = BytesIO(pdf_blob.download_as_bytes())
        reader = PyPDF2.PdfReader(pdf_data)
        writer = PyPDF2.PdfWriter()
        for page_num in taxonomy_page_no:
            page = reader.pages[int(page_num)]
            writer.add_page(page)
        # Write the extracted pages back to GCS
        output_pdf_data = BytesIO()
        writer.write(output_pdf_data)
        output_pdf_blob = client.bucket(output_bucket_name).blob(
            f"{output_folder}/{source_pdf_name}_extracted.pdf"
        )
        output_pdf_blob.upload_from_string(
            output_pdf_data.getvalue(), content_type="application/pdf"
        )
        print(
            f"Pages {', '.join(map(str, taxonomy_page_no))} extracted to {output_pdf_blob.path}."
        )


def get_column_name_type_using_xcoord(
    value: int, processed_map: Dict[str, List[int]]
) -> Tuple[Union[str, None], Union[List[str], None]]:
    """
    This method returns the name of the column by its horizontal location
    It would need to be set on a per-carrier basis and adjusted if the reports
    change. Because some cell values span columns we can't auto-detect columns
    by drawing vertical lines down the page in places where they don't intersect
    with text.
    """

    for col, threshold in dict(
        sorted(processed_map.items(), key=lambda item: item[1])
    ).items():
        if threshold[0] <= value <= threshold[1]:
            col_string = col.split("_")
            if "DNSH" in col_string or "safeguards" in col_string:
                return col, ["Y", "N", "N/A", "S", "n/a"]
            if "SCC" in col_string or "proportion" in col_string:
                return col, ["%"]
            if "business" in col_string:
                return col, ["number"]
            if "code" in col_string:
                return col, ["code"]
            return col, None
    return None, None


def get_entire_row(
    page: documentai.Document.Page,
    block: documentai.Document.Page.Block,
    dest_df: pd.DataFrame,
    document_response: documentai.Document,
    blockn: int,
    height: float,
    width: float,
    processed_map: Dict[str, List[int]],
) -> None:
    """
    Method finds the start of each row and then moves through it, collecting columns as it goes.
    Args:
        page (documentai.Document.Page): Document page.
        block (documentai.Document.Page.Block): Document block.
        dest_df (pd.DataFrame): Destination DataFrame to store extracted information.
        document_response (documentai.Document): Document response.
        blockn (int): Block number.
        height (float): Height of the document page.
        width (float): Width of the document page.
        processed_map (Dict[str, List[int]]): Processed map.
    Returns:
        None
    """

    y_values = [
        round(vertex.y * height)
        for vertex in block.layout.bounding_poly.normalized_vertices
    ]
    min_y = min(y_values)
    max_y = max(y_values)
    idx = len(dest_df)
    # col = 0
    col_block = {
        col: blockn + i for i, col in zip(range(dest_df.shape[1]), dest_df.columns)
    }
    col_occurence = {}
    for bn, block in enumerate(page.blocks):
        # get the min and max y values for each block
        y_values = [
            round(vertex.y * height)
            for vertex in block.layout.bounding_poly.normalized_vertices
        ]
        this_min_y = min(y_values) + 5
        this_max_y = max(y_values) - 5
        # compare if the block coordinates falls under required row block
        if this_min_y >= min_y and this_max_y <= max_y:
            block_text = layout_to_text(block.layout, document_response.text)
            x_valuesn = [
                round(vertex.x * width)
                for vertex in block.layout.bounding_poly.normalized_vertices
            ]
            # this_max_x = round(max(x_valuesn) / 10)
            this_max_x = math.ceil(max(x_valuesn) / 10)
            # get the column name corresponding to the x coordinate
            column, col_type = get_column_name_type_using_xcoord(
                this_max_x, processed_map
            )
            # extract columns specified in CDE
            if column:
                if col_type == ["number"]:
                    block_text = get_matched_field(
                        block_text,
                        pattern=r"(^\(\d+\))|(\d+[,|]\d+)|(^\(\d+,\d+\))|(\d+)",
                    )
                elif col_type == ["%"]:
                    block_text = get_matched_field(
                        block_text, pattern=r"([0-9]+)|([0-9]+[|%])([0-9]+[|%])"
                    )
                elif block_text.replace("\n", "") in ["Y", "N", "N/A", "S", "n/a"]:
                    block_text = get_matched_field(
                        block_text, pattern="(N/A|Y|N|S|n/a)"
                    )
                elif col_type == ["code"]:
                    block_text = get_matched_field(
                        block_text,
                        pattern=r"([0-9]+\.[0-9]+\/[0-9]+\.[0-9]+)|([0-9]+\.[0-9]+)",
                    )
                elif column != "taxonomy_disclosure":
                    block_text = (
                        ""  # there are random characters in different block (즘)
                    )
                try:
                    dest_df.loc[idx, column] += (
                        " " + block_text
                    )  # add space between 2 blocks text
                    # col_occurence[column] += 1
                except (TypeError, KeyError):
                    dest_df.loc[idx, column] = block_text
                    col_occurence[column] = 1
                    if bn > col_block[column]:
                        dest_df.loc[idx, column] = "-\n" + block_text
                    # else:
                    #   dest_df.loc[idx, column] = block_text


def is_table_region(
    layout: documentai.Document.Page.Layout, ystart: int, yend: int, height: float
) -> bool:
    """
    Get rows from a particular range.
    Args:
        layout (documentai.Document.Page.Layout): Layout information for the region.
        ystart (int): Starting y-coordinate for the table region.
        yend (int): Ending y-coordinate for the table region.
        height (float): Height of the document page.
    Returns:
        bool: True if the layout region corresponds to a table region, False otherwise.
    """

    y_values = [
        round(vertex.y * height) for vertex in layout.bounding_poly.normalized_vertices
    ]
    min_y = min(y_values)
    max_y = max(y_values)
    if min_y >= ystart and max_y <= yend:
        return True
    return False


def get_table_data(
    document_fp: documentai.Document,
    processed_map: Dict[int, Dict[str, List[int]]],
    ycord: Dict[int, List[int]],
) -> Dict[int, pd.DataFrame]:
    """
    Parse the Form parser OCR output to reconstruct the table.
    Args:
        document_fp (documentai.Document): Document containing OCR output.
        processed_map (Dict[int, Dict[str, List[int]]]): Processed map for coordinates.
        ycord (Dict[int, List[int]]): Y-coordinates for each page.
    Returns:
        Dict[int, pd.DataFrame]: Dictionary of DataFrames, where keys are page numbers.
    """

    df_list = {}
    for pgn, page in enumerate(document_fp.pages):
        dimension = document_fp.pages[pgn].dimension
        width, height = dimension.width, dimension.height
        dest_df3 = pd.DataFrame(
            columns=list(
                dict(
                    sorted(processed_map[pgn].items(), key=lambda item: item[1])
                ).keys()
            )
        )
        ypgn = ycord[pgn]
        ystart, yend = ypgn[0] - 2, ypgn[-1] + 2
        for bn, block in enumerate(page.blocks):
            block_text = layout_to_text(block.layout, document_fp.text)
            if not is_table_region(block.layout, ystart, yend, height):
                continue
            activity = re.search(
                r"(^\d.\d+(.|) [a-zA-Z\s]+)|"
                "(^Total)|"
                "(^Sum[a-zA-Z1-9\\.+\\s]+)|"
                "(^Revenue ([a-z]+))|"
                "(^[A-Z]\\.[1-9|\\s][a-zA-Z0-9\\s\\.-]+)|"
                "(^OPEX ([a-z]+))|"
                "(^CAPEX ([a-z]+))|"
                "(^Taxonomy ([a-z]+)|"
                "^[A-Z]+[a-z]+)",
                block_text,
            )
            if activity:
                # activity detected: table row
                get_entire_row(
                    page,
                    block,
                    dest_df3,
                    document_fp,
                    bn,
                    height,
                    width,
                    processed_map[pgn],
                )
        df_list[pgn] = dest_df3
    return df_list


def update_data(
    final_df_: pd.DataFrame, final_data_: DefaultDict[str, List[str]], ea: str
) -> DefaultDict[str, List[str]]:
    """
    Update the final dataframe.
    Args:
        final_df_ (pd.DataFrame): DataFrame containing the final data.
        final_data_ (DefaultDict[str, List[str]]): DefaultDict to be updated.
        ea (str): Value to be added to the "taxonomy_disclosure" column.
    Returns:
        DefaultDict[str, List[str]]: Updated defaultdict.
    """

    for column in final_df_.columns:
        if column == "taxonomy_disclosure":
            final_data_[column].append(ea)
        else:
            final_data_[column].append("")
    return final_data_


def post_process(
    dest_df: pd.DataFrame, col: str, processed_map: Dict[str, List[int]]
) -> DefaultDict[str, List[str]]:
    """
    Process the final dataframe to remove noise from the data.
    """

    final_df_ = pd.DataFrame(
        columns=list(
            dict(sorted(processed_map.items(), key=lambda item: item[1])).keys()
        )
    )
    # Post-processing code matches expected values and rearranges them into the final dataframe
    final_data_: DefaultDict[str, List[str]] = defaultdict(list)
    for _, row in dest_df.iterrows():
        if row["taxonomy_disclosure"] is np.nan:
            continue
        st = row["taxonomy_disclosure"]
        # search for taxonomy pattern
        ea = re.search(r"^[A-Z]\.\s[a-zA-Z\s-]+", st)
        if ea:
            span = ea.span()
            interstr = st[span[0] : span[1]].split("\n")[0]
            st = st.replace(interstr + "\n", "").strip()
            final_data_ = update_data(final_df_, final_data_, interstr)
            row["taxonomy_disclosure"] = st
        st = row["taxonomy_disclosure"]
        ea = re.search(r"^[A-Z]\.[1-9](.|)[a-zA-Z()\s-]+", st)
        if ea:
            span = ea.span()
            interstr = st[span[0] : span[1]].split("\n")[0:-1]
            ans = " ".join(interstr)
            st = st.replace(st[span[0] : span[1]], "")
            final_data_ = update_data(final_df_, final_data_, ans)
            row["taxonomy_disclosure"] = st
        st = row["taxonomy_disclosure"]
        row_ea = re.findall(r"\d.\d+ [a-zA-Z\s]+", st)
        if len(row_ea) > 1:
            row["taxonomy_disclosure"] = "\n".join(
                [ea.replace("\n", " ").strip() for ea in row_ea]
            )
        try:
            # collect values if particular col(business measure) has more than one value
            split_row = []
            for val in row[col].split("\n"):
                try:
                    if re.search(r"^[0-9]+(.|,)[0-9]+", val):
                        split_row.append(val)
                except ValueError:
                    pass
            n = len(split_row)
            for column in final_df_.columns:
                try:
                    if n > 1:
                        column_data = [data for data in row[column].split("\n") if data]

                        # if no. of values in particular column doesn't match with n
                        diff = n - len(column_data)
                        if diff != 0:
                            column_data.extend([np.nan] * diff)
                        final_data_[column].extend(column_data)
                    else:
                        # remove `-` character
                        val = row[column].replace("\n", " ").strip()
                        if column != "taxonomy_disclosure":
                            val = val.replace("-", "").strip()

                        final_data_[column].extend([val])
                except ValueError:
                    final_data_[column].extend([np.nan] * n)
        except ValueError:
            ea_ = row["taxonomy_disclosure"].replace("\n", " ")
            final_data_ = update_data(final_df_, final_data_, ea_)
    return final_data_


def run_table_extractor_pipeline(
    offset: int,
    project_id: str,
    location: str,
    gcs_output_bucket: str,
    gcs_output_uri_prefix: str,
    document_fp: documentai.Document,
    row_map: Dict[int, Dict[str, List[int]]],
    filen: str,
    ycord: Dict[int, List[int]],
    col: str = "business_measure",
) -> Union[pd.Series, pd.DataFrame]:
    """
    Function to parse the data extracted from FP and map with CDE headers
    and store the final output as csv in the GCS bucket.
    """

    processed_map = get_processed_map(row_map, offset)
    df_list = get_table_data(document_fp, processed_map, ycord)
    filen_ = filen[:-4]
    for pgn, df in df_list.items():
        final_data_new2 = post_process(
            df.copy(), col=col, processed_map=processed_map[pgn]
        )
        final_data_2_processed = final_data_new2.copy()
        nrows = 0  # num of rows
        for _, v in final_data_new2.items():
            nrows = max(len(v), nrows)

        for _, v in final_data_2_processed.items():
            length = len(v)
            if length != nrows:
                v.extend([np.nan] * (nrows - length))
        taxonomy_data: Union[pd.Series, pd.DataFrame] = pd.DataFrame(
            final_data_2_processed
        )
        taxonomy_data = (
            taxonomy_data[taxonomy_data != ""].dropna(how="all").reset_index(drop=True)
        )
        taxonomy_data.to_csv(
            f"gs://{gcs_output_bucket}/{gcs_output_uri_prefix}/{filen_}/{pgn}.csv",
            index=False,
        )
    print("Extraction completed")
    return taxonomy_data


def walk_the_ocr(
    project_id: str,
    location: str,
    cde_input_output_map: Dict[str, Dict[str, str]],
    gcs_output_bucket: str,
    gcs_cde_hitl_output_prefix: str,
    fp_input_output_map: Dict[str, str],
    gcs_output_uri_prefix: str,
    offset: int,
) -> None:
    """
    Main function to read CDE and FP json output and parse it to get final output.
    """

    for file, data in cde_input_output_map.items():
        print("File:", file)
        if data.get("hitl", None):
            operation = data["hitl"]
            cde_jsons = read_json_output(
                output_bucket=gcs_output_bucket,
                output_prefix=f"{gcs_cde_hitl_output_prefix}/{operation}",
                hitl=True,
            )
            cde_document = cde_jsons[operation]
            print("HITL")
        else:
            cde_jsons = read_json_output(
                output_bucket=gcs_output_bucket, output_prefix=data["cde"]
            )
            cde_document = cde_jsons[file[:-4]]
            print("NO HITL")
        _, y_coord, row_map_cde, _ = get_coordinates_map(cde_document)
        fp_document_path = fp_input_output_map[file]
        fp_document = read_json_output(
            output_bucket=gcs_output_bucket, output_prefix=fp_document_path
        )
        run_table_extractor_pipeline(
            offset=offset,
            project_id=project_id,
            location=location,
            gcs_output_bucket=gcs_output_bucket,
            gcs_output_uri_prefix=gcs_output_uri_prefix,
            document_fp=fp_document[file[:-4]],
            row_map=row_map_cde,
            filen=file,
            ycord=y_coord,
        )


def enhance_and_save_pdfs(
    output_bucket: str,
    gcs_cde_hitl_output_prefix: str,
    line_enhance_prefix: str,
    cde_input_output_map: Dict[str, Dict[str, str]],
    voffset_: int,
    hoffset_: Union[int, float],
    factor: float = 0.75,
):
    """
    Enhance the table structure by drawing the lines based on CDE output,
    headers and rows coordinates.
    """

    # Initialize Google Cloud Storage client
    storage_client = storage.Client()
    bucket = storage_client.bucket(output_bucket)
    voffset = voffset_
    hoffset = hoffset_
    line_width = 5
    line_colour = "black"
    for file, data in cde_input_output_map.items():
        print("File:", file)
        file_key = file[:-4]
        if data.get("hitl", None):
            operation = data["hitl"]
            cde_jsons = read_json_output(
                output_bucket=output_bucket,
                output_prefix=f"{gcs_cde_hitl_output_prefix}/{operation}",
                hitl=True,
            )
            document = cde_jsons[operation]
            print("HITL")
        else:
            cde_jsons = read_json_output(
                output_bucket=output_bucket, output_prefix=data["cde"]
            )
            document = cde_jsons[file_key]
            print("NO HITL")
        try:
            images_for_pdf = []
            for idx, page in enumerate(document.pages):
                x_coordinates, _, _, max_ycd = get_coordinates_map(document)
                image_content = page.image.content
                image = PilImage.open(BytesIO(image_content))
                draw = ImageDraw.Draw(image)
                min_height, max_height = max_ycd[idx][0], max_ycd[idx][-1]
                min_x, max_x = x_coordinates[idx][0][0], x_coordinates[idx][-1][1]
                hoffset_ = factor * voffset
                # Draw horizontal
                if idx in max_ycd:
                    for n, y in enumerate(max_ycd[idx]):
                        if n == 0:  # column header min y coord
                            draw.line(
                                (
                                    min_x - (1 * hoffset),
                                    min_height - hoffset_,
                                    max_x + (1.5 * hoffset),
                                    min_height - hoffset_,
                                ),
                                fill=line_colour,
                                width=line_width,
                            )
                        else:
                            draw.line(
                                (
                                    min_x - (2 * hoffset),
                                    y + hoffset,
                                    max_x + (1.5 * hoffset),
                                    y + hoffset,
                                ),
                                fill=line_colour,
                                width=line_width,
                            )
                # Drawing vertical lines
                if idx in x_coordinates:
                    for n, cor in enumerate(x_coordinates[idx]):
                        if n == 0:
                            draw.line(
                                [
                                    (cor[0] - hoffset_, min_height - hoffset_),
                                    (cor[0] - hoffset_, max_height + hoffset_),
                                ],
                                fill=line_colour,
                                width=line_width,
                            )
                        if (
                            n + 1 < len(x_coordinates[idx])
                            and (x_coordinates[idx][n + 1][1] + voffset // 2)
                            - (cor[1] + voffset // 2)
                            > 50
                        ):
                            draw.line(
                                [
                                    (cor[1] + voffset // 2, min_height - hoffset_),
                                    (cor[1] + voffset // 2, max_height + hoffset_),
                                ],
                                fill=line_colour,
                                width=line_width,
                            )
                        elif n + 1 == len(x_coordinates[idx]):
                            draw.line(
                                [
                                    (cor[1] + voffset // 2, min_height - hoffset_),
                                    (cor[1] + voffset // 2, max_height + hoffset_),
                                ],
                                fill=line_colour,
                                width=line_width,
                            )
                # Append modified image to the list
                images_for_pdf.append(image)
            # Save images to a single PDF
            pdf_stream = BytesIO()
            images_for_pdf[0].save(
                pdf_stream,
                save_all=True,
                append_images=images_for_pdf[1:],
                resolution=100.0,
                quality=95,
                optimize=True,
                format="PDF",
            )
            # Upload PDF to Google Cloud Storage
            blob = bucket.blob(f"{line_enhance_prefix}/{file_key}.pdf")
            blob.upload_from_string(
                pdf_stream.getvalue(), content_type="application/pdf"
            )
            print(f"Done Processing -{file_key}.pdf")
        except ValueError:
            print(traceback.format_exc())
            print(f"Issue with processing -{file_key}.pdf")
            images_for_pdf = []
            for idx, page in enumerate(document.pages):
                image_content = page.image.content
                image = PilImage.open(BytesIO(image_content))
                draw = ImageDraw.Draw(image)
                # Append original image to the list
                images_for_pdf.append(image)

            # Save images to a single PDF
            pdf_stream = BytesIO()
            images_for_pdf[0].save(
                pdf_stream,
                save_all=True,
                append_images=images_for_pdf[1:],
                resolution=100.0,
                quality=95,
                optimize=True,
                format="PDF",
            )
            # Upload PDF to Google Cloud Storage
            blob = bucket.blob(f"{line_enhance_prefix}/{file_key}.pdf")
            blob.upload_from_string(
                pdf_stream.getvalue(), content_type="application/pdf"
            )
    print("Completed Preprocessing")
