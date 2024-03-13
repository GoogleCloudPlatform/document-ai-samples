# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# pylint: disable=R1702
# pylint: disable=R0912
# pylint: disable=R0913
# pylint: disable=R0914
# pylint: disable=R0915
# pylint: disable=E0401
# pylint: disable=C0302
"""This module contains helper functions for Backmapping Tool"""
import base64
from collections import defaultdict
import io
import json
import os
import re
from typing import Any, Dict, List, MutableSequence, Optional, Tuple, Union

import cv2
from dateutil.parser import parse
from fuzzywuzzy import fuzz
from google import auth
import google.auth.transport.requests
from google.cloud import documentai_v1beta3 as documentai
from google.cloud import storage
import numpy
import pandas as pd
from PIL import Image
import requests


def get_access_token() -> Union[str, Any]:
    """
    Retrieves and returns an access token for API authentication.
    Returns:
        str: access token.
    """
    credentials, _ = auth.default()
    credentials.refresh(google.auth.transport.requests.Request())
    token = credentials.token
    return token


def download_pdf(gcs_input_path: str, file_prefix: str) -> bytes:
    """
    Reads the PDF file from Google Cloud Storage (GCS).
    Args:
        gcs_input_path (str): GCS document path.
        file_prefix (str): Prefix for the GCS document name.
    Returns:
        pdf_content (bytes): bytes object containing the PDF content.
    """
    client = storage.Client()
    bucket_name = gcs_input_path.split("/")[2]
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_prefix)
    pdf_content = blob.download_as_bytes()
    return pdf_content


def process_document(
    project_id: str,
    location: str,
    processor_id: str,
    processor_version: str,
    file_content: Optional[bytes] = None,
    file_uri: Optional[str] = None,
    mime_type: str = "application/pdf",
    is_native: Optional[bool] = False,
    ocr: Optional[bool] = True,
) -> documentai.Document:
    """
    This function processes a document using either PDF content in bytes or a GCS file URI.
    Args:
        project_id (str): The project ID for Google Cloud services.
        location (str): The location of the Google Cloud project.
        processor_id (str): The ID of the processor to use.
        processor_version (str): The version of the processor to use.
        file_content (bytes): PDF document content in bytes.
        file_uri (str): GCS file path.
        mime_type (str): Type of document, e.g., application/pdf.
        is_native (bool): True, if the input PDF is native.
        ocr (bool): True, if running OCR processor.
    Returns:
        documentai.Document: Parsed JSON data of the document as Document-object.
    """
    opts = {"api_endpoint": f"{location}-documentai.googleapis.com"}
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    name = client.processor_version_path(
        project_id, location, processor_id, processor_version
    )
    if file_content:
        document = documentai.RawDocument(content=file_content, mime_type=mime_type)
    elif file_uri:
        document = documentai.GcsDocument(gcs_uri=file_uri, mime_type=mime_type)
    else:
        raise ValueError("Either 'file_content' or 'file_uri' must be provided.")
    process_options = None
    if ocr:
        ocr_config = documentai.OcrConfig(
            enable_native_pdf_parsing=is_native,
            enable_image_quality_scores=True,
            enable_symbol=True,
        )
        process_options = documentai.ProcessOptions(ocr_config=ocr_config)
    raw_doc = document if file_content else None
    gcs_doc = document if file_uri else None
    request = documentai.ProcessRequest(
        name=name,
        raw_document=raw_doc,
        gcs_document=gcs_doc,
        skip_human_review=True,
        process_options=process_options,
    )
    result = client.process_document(request=request)
    return result.document


def document_to_json(result: documentai.Document) -> Dict[str, Any]:
    """
    Converts a Document AI process response to a JSON-friendly format.
    Args:
        result (documentai.Document): The result object from Document AI processing.
    Returns:
        Dict[str, Any]: A dictionary representing the JSON format of the processed document.
    """
    # Convert the result to a JSON-friendly format
    with io.BytesIO() as _:
        a = io.BytesIO()
        a.write(bytes(documentai.Document.to_json(result), "utf-8"))
        a.seek(0)
        json_string = a.read().decode("utf-8")
        json_data = json.loads(json_string)
    return json_data


def upload_to_cloud_storage(
    filename: str,
    data: Union[bytes, Dict[str, Any], pd.DataFrame],
    output_bucket: str,
    output_prefix: str,
) -> None:
    """
    Uploads the document to GCS.
    Args:
        filename: File name.
        data: Bytes, JSON data, or DataFrame to store as a file.
        output_bucket: GCS Bucket name.
        output_prefix: GCS prefix where to store the file.
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(output_bucket)
    gcs_uri = f"gs://{output_bucket}/{output_prefix}/{filename}"
    blob = bucket.blob(f"{output_prefix}/{filename}")
    if isinstance(data, bytes):
        # Upload bytes as a file
        blob.upload_from_string(data, content_type="application/pdf")
        print(f"\tSaved the PDF document to GCS: {gcs_uri}")
    elif isinstance(data, dict):
        # Convert dictionary to JSON string and upload
        json_string = json.dumps(data)
        blob.upload_from_string(json_string, content_type="application/json")
        print(f"\tSaved the JSON data to GCS: {gcs_uri}")
    elif isinstance(data, pd.DataFrame):
        # Convert DataFrame to CSV format and upload
        csv_content = data.to_csv(index=False)
        blob.upload_from_string(csv_content, content_type="text/csv")
        print(f"\tSaved the DataFrame to GCS: {gcs_uri}")
    else:
        print("\tUnsupported data type for upload")


def get_redact_bbox_from_text(
    text_redact: str, full_text: str, json_data: documentai.Document
) -> Dict[str, List[List[Any]]]:
    """
    Extracts the bounding box from the given document for a specific text to redact.
    Args:
        text_redact (str): The text to redact.
        full_text (str): The full text content of the document.
        json_data (documentai.Document): The processed Document AI document.
    Returns:
        Dict[str, List[List[Any]]]:
            A dictionary containing page numbers as keys and a list of
            bounding boxes as values.
            Bounding box format: [x_min, y_min, x_max, y_max].
    """
    part1 = re.escape(text_redact.split(" ")[0])
    part2 = re.escape(text_redact.split(" ")[-1])
    pattern = f"{part1}.*{part2}"
    matches = re.finditer(pattern, full_text, flags=re.IGNORECASE)

    redact_bbox = {}
    for match in matches:
        start, end = match.span()
        for page_num, page in enumerate(json_data.pages):
            x, y = [], []
            for token in page.tokens:
                if token.layout.text_anchor.text_segments:
                    si = token.layout.text_anchor.text_segments[0].start_index
                    ei = token.layout.text_anchor.text_segments[0].end_index
                    if si >= start and ei <= end:
                        norm_ver = token.layout.bounding_poly.normalized_vertices
                        x.extend([ver.x for ver in norm_ver])
                        y.extend([ver.y for ver in norm_ver])

            if x and y:  # Check if x and y have been modified
                bbox = [min(x), min(y), max(x), max(y)]
                redact_bbox[str(page_num)] = [bbox]

    return redact_bbox


def get_synthesized_images(json_data: documentai.Document) -> List[Image.Image]:
    """
    Convert JSON data into a list of images.
    Args:
        json_data (documentai.Document): Document AI JSON data.
    Returns:
        List[Image.Image]: List of synthesized images.
    """
    synthesized_images = []

    def decode_image(image_bytes: bytes) -> Image.Image:
        with io.BytesIO(image_bytes) as image_file:
            image = Image.open(image_file)
            image.load()
        return image

    for page in json_data.pages:
        synthesized_images.append(decode_image(page.image.content))
    return synthesized_images


def draw_black_box(
    synthesized_images: List[Image.Image],
    page_wise_bbox: Any,
) -> io.BytesIO:
    """
    Draw black boxes around PII entities in synthesized images and add synthetic data.
    Args:
        synthesized_images (List[Image.Image]): List of synthesized images.
        page_wise_bbox (Any): Dictionary with page-wise bounding boxes.
    Returns:
        io.BytesIO: Byte stream containing the final PDF with black boxes drawn.
    """
    open_cv_image = {}
    for idx, _ in enumerate(synthesized_images):
        open_cv_image[idx] = numpy.array(synthesized_images[idx].convert("RGB"))
    img_final = []
    for i, image in open_cv_image.items():
        size = image.shape
        for page, bbox_list in page_wise_bbox.items():
            if str(i) == page:
                for bbox in bbox_list:
                    x1 = int(bbox[0] * size[1])
                    y1 = int(bbox[1] * size[0])
                    x2 = int(bbox[2] * size[1])
                    y2 = int(bbox[3] * size[0])
                    cv2.rectangle(
                        image,
                        (x1, y1),
                        (x2, y2),
                        (255, 255, 255),
                        thickness=cv2.FILLED,
                    )
        img_temp = Image.fromarray(image)
        img_final.append(img_temp)
    pdf_stream = io.BytesIO()
    img_final[0].save(
        pdf_stream,
        save_all=True,
        append_images=img_final[1:],
        resolution=100.0,
        quality=95,
        optimize=True,
        format="PDF",
    )
    return pdf_stream


def redact(
    project_id: str,
    location: str,
    processor_version: str,
    processor_id: str,
    pdf_bytes: bytes,
    mime_type: str = "application/pdf",
) -> bytes:
    """
    Main function to process documents, redact PII entities, and store the result.
    Args:
        project_id (str): GCP project id.
        location (str): Location of the docai processor.
        processor_version (str): DocAI processor version.
        processor_id (str): DocAI processor id.
        pdf_bytes (bytes): PDF document bytes to process.
        mime_type (str, optional): Type of document, e.g., "application/pdf".
            Defaults to "application/pdf".
    Returns:
        bytes: Redacted PDF document bytes.
    """
    redact_text = ["Machine Translated by Google"]
    json_data = process_document(
        project_id,
        location,
        processor_id,
        processor_version,
        pdf_bytes,
        None,
        mime_type,
        False,
        False,
    )
    redact_bbox: Dict[str, Any] = {}
    try:
        for t1 in redact_text:
            page_wise_bbox_text = get_redact_bbox_from_text(
                t1, json_data.text, json_data
            )
            for p1, b1 in page_wise_bbox_text.items():
                if p1 in redact_bbox:
                    redact_bbox[p1].extend(b1)
                else:
                    redact_bbox[p1] = b1
    except ValueError:
        pass
    synthesized_images = get_synthesized_images(json_data)
    pdf_stream = draw_black_box(synthesized_images, redact_bbox)
    redacted_pdf_stream = pdf_stream.getvalue()
    return redacted_pdf_stream


def get_min_max_x_y(
    bounding_box: MutableSequence[documentai.NormalizedVertex],
) -> Tuple[float, float, float, float]:
    """
    Function returns min-max x & y coordinates from the entity bounding box.
    Args:
        bounding_box (MutableSequence[documentai.NormalizedVertex]):
            A list of vertices representing the bounding bo
    Returns:
        min_max_x_y (Tuple[float, float, float, float]):
            Minimum and maximum x,y coordinates of entity bounding box.
    """
    min_x = min(item.x for item in bounding_box)
    min_y = min(item.y for item in bounding_box)
    max_x = max(item.x for item in bounding_box)
    max_y = max(item.y for item in bounding_box)
    min_max_x_y = (min_x, max_x, min_y, max_y)
    return min_max_x_y


def get_normalized_vertices(
    coords: Dict[str, float]
) -> MutableSequence[documentai.NormalizedVertex]:
    """
    It takes XY-Coordinates & creates normalized-verices for Document Object
    Args:
        coords (Dict[str, float]): It contains min&max xy-coordinates
    Returns:
        MutableSequence[documentai.NormalizedVertex]:
            It returns list containing 4 NormalizedVertex Objects
    """
    coords_order = [
        ("min_x", "min_y"),
        ("max_x", "min_y"),
        ("max_x", "max_y"),
        ("min_x", "max_y"),
    ]
    nvs = []
    for x, y in coords_order:
        nvs.append(documentai.NormalizedVertex(x=coords[x], y=coords[y]))
    return nvs


def get_formatted_dates(main_string: str) -> Dict[str, str]:
    """
    This function checks for dates in the given string and returns them in a specific format.
    Args:
        main_string (str): The input string containing dates.
    Returns:
        formatted_dates(Dict[str, str]):
            A dictionary containing original dates as keys and formatted dates as values.
    """
    # Regular expression pattern to find dates
    date_pattern = (
        r"\b(?:\d{1,2}\/\d{1,2}\/\d{2,4}|\d{1,2}-\d{1,2}-\d{2,4}|"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2} \d{4}|"
        r"(?:\d{1,2}\.\d{1,2}\.\d{2,4}|\d{1,2}\.\d{2}\.\d{2}))\b"
    )
    # Find and format matching dates in the main string
    dates = re.findall(date_pattern, main_string.replace("/n", " "))
    formatted_dates = {}
    for date_str in dates:
        try:
            date_obj = parse(date_str, fuzzy=True)
            formatted_date = date_obj.strftime("%d/%m/%Y")
            formatted_dates[date_str] = formatted_date
        except ValueError:
            # Handle invalid date formats gracefully
            pass
    return formatted_dates


def find_matched_translation_pairs(
    entity: documentai.Document.Entity, translation_api_output: List[Dict[str, str]]
) -> List[Dict[str, str]]:
    """
    Function returns the best mapping text pairs with entity mention text.
    Args:
        entity (documentai.Document.Entity): Document AI extracted entity dictionary.
        translation_api_output (List[Dict[str, str]])):
            Mapping dictionary of source and corresponding translated text.
    Returns:
        best_match_pairs (List[Dict[str, str]]):
            Pairs which are best matched with entity mention text.
    """
    pattern = r"^[0-9,.\n \\]*$"
    regex = re.compile(pattern)
    ent_mt = entity.mention_text
    if regex.match(ent_mt):
        best_match_pairs = [{"sourceText": ent_mt, "targetText": ent_mt}]
    else:

        def similar(a, b):
            return fuzz.ratio(a, b)

        target_lines = ent_mt.split("\n")
        best_match_pairs = []
        for target_line in target_lines:
            best_match_score = 0
            best_match_pair = None
            for entry in translation_api_output:
                target_text = entry["targetText"]
                similarity_score = similar(target_line.strip(), target_text.strip())
                if similarity_score > best_match_score:
                    best_match_score = similarity_score
                    best_match_pair = entry
            if best_match_pair:
                best_match_pairs.append(best_match_pair)
    return best_match_pairs


def get_page_text_anc_mentiontext(
    entity: documentai.Document.Entity,
    orig_invoice_json: documentai.Document,
    min_max_x_y: Tuple[float, float, float, float],
    mapping_text: str,
    diff_y: float,
    diff_x: float,
    english_page_num: int,
) -> Tuple[Any, Dict[str, Dict[Any, Any]], str, List[List[str]], str,]:
    """
    Function returns the min-max coordinates, text anchors and mention text of backmapped entity
    using provided extracted source entity, corresponding x&y coordinates, and
    mapping text from translation api output, with coordinate offset check.
    Args:
        entity (documentai.Document.Entity): Document AI extracted entity dictionary.
        orig_invoice_json (documentai.Document): Original document Invoice processor json output.
        min_max_x_y (Tuple[float, float, float, float]):
            Minimum and maximum x&y coordinates of entity bounding box.
        mapping_text (str): Source text from translation text units.
        diff_y (float): Y-coordinate offset.
        diff_x (float): X-coordinate offset.
        english_page_num (int): Document page number.
    Returns:
        Tuple[
            Any,
            Dict[str, Dict[Any, Any]],
            str,
            List[List[str]],
            str
        ]
            - bbox (Dict[str, float]):
                Dictionary containing min-max x&y coordinates of the mapped entity.
            - expected_text_anc (Dict[
                str,
                str]
            ]):
                List of start and end indexes of the mapped entity.
            - new_mention_text (str): Mapped entity text.
            - match_string_pair (List[List[str]]): List of matched string pairs.
            - method (str): Based on mapping block.
    """
    min_x, _, min_y, _ = min_max_x_y
    matches: List[Any] = []
    match_string_pair: List[Any] = []
    method = ""
    # Track whether entity is matched from OCR or Translated units
    orig_text = orig_invoice_json.text
    try:
        matches, match_string_pair = find_substring_indexes(
            orig_text, entity.mention_text
        )
        if matches:
            method = "OCR-EntityMT"
    except ValueError:
        matches, match_string_pair = find_substring_indexes(orig_text, mapping_text)
        if matches:
            method = "OCR-TU"
    if not matches:
        matches, match_string_pair = find_substring_indexes(orig_text, mapping_text)
        if matches:
            method = "OCR-TU"
        if not matches:
            dates_german_text = get_formatted_dates(orig_text)
            ent_date = get_formatted_dates(entity.mention_text)
            matched_dates = defaultdict(list)
            for k1, v1 in ent_date.items():
                for k2, v2 in dates_german_text.items():
                    if v1 == v2:
                        matched_dates[k1].append(k2)
            for _, mat_1 in matched_dates.items():
                for mat_11 in mat_1:
                    match_temp, match_string_pair_temp = find_substring_indexes(
                        orig_text, mat_11
                    )
                    for mat_2, str_pair in zip(match_temp, match_string_pair_temp):
                        matches.append(mat_2)
                        match_string_pair.append(str_pair)
            if matches:
                method = "OCR-EntityMT"
    # Initialize variables.
    bbox, text_anc_1, new_mention_text, expected_text_anc = {}, {}, "", {}
    # Iterate through match pairs.
    for match, str_pair in zip(matches, match_string_pair):
        try:
            _ts = documentai.Document.TextAnchor.TextSegment(
                start_index=int(match[0]), end_index=int(match[1])
            )
            bb, text_anc = get_token(orig_invoice_json, english_page_num, [_ts])
        except ValueError:
            continue
        # bb can have empty string return by get_token
        if not bb:
            continue
        # Difference between the original and mapped bbox should be within defined offset.
        cond1, cond2 = (
            abs(bb["min_y"] - min_y) <= diff_y,
            abs(bb["min_x"] - min_x) <= diff_x,
        )
        if cond1 and cond2:
            diff_x = abs(bb["min_x"] - min_x)
            diff_y = abs(bb["min_y"] - min_y)
            bbox = bb
            text_anc_1 = text_anc
            for index, an3 in enumerate(text_anc_1):
                si = an3.start_index
                ei = an3.end_index
                ent_text = orig_text[si:ei]
                cond1 = index in [0, len(text_anc_1) - 1]
                cond2 = ent_text.strip() in [")", "(", ":", " ", "/", "\\"]
                if cond1 and cond2:
                    continue
                new_mention_text += ent_text
            expected_text_anc = {"textSegments": text_anc_1}
    return bbox, expected_text_anc, new_mention_text, match_string_pair, method


def updated_entity_secondary(
    orig_invoice_json: documentai.Document,
    min_max_x_y: Tuple[float, float, float, float],
    mapping_text: str,
    english_page_num: int,
) -> Tuple[Any, Any, str, List[List[Any]], str,]:
    """
    Function returns the min-max coordinates, text anchors and mention text of backmapped entity
    using provided extracted source entity x&y coordinates, and
    mapping text from translation api output, with original document tokens.
    Args:
        orig_invoice_json (documentai.Document): Original document Invoice processor json output.
        min_max_x_y (Tuple[float, float, float, float]):
            Minimum and maximum x&y coordinates of entity bounding box.
        mapping_text (str): Source text from translation text units.
        english_page_num (int): Document page number.
    Returns:
        - Tuple[
            Any,
            Any,
            str,
            List[List[Any]],
            str
        ]:
        - updated_page_anc (Any):
            Dictionary containing min-max x&y coordinates of the mapped entity.
        - updated_text_anc (Any):
            List of start and end indexes of the mapped entity..
        - mentiontext (str): Mapped entity text.
        - match_string_pair (List[List[Any]]): List of matched string pairs.
        - method (str): Based on mapping block.
    """
    min_x, max_x, min_y, max_y = min_max_x_y
    text_anc_tokens = []
    confidence = []
    page_anc: Dict[str, List[float]] = {"x": [], "y": []}
    mapping_list = mapping_text.split()
    method = "OCR-TU"
    match_string_pair = []
    for token in orig_invoice_json.pages[english_page_num].tokens:
        norm_vert = token.layout.bounding_poly.normalized_vertices
        new_min_x, new_max_x, new_min_y, new_max_y = get_min_max_x_y(norm_vert)
        cond11 = abs(new_min_y - min_y) <= 0.01
        cond12 = abs(new_max_y - max_y) <= 0.01
        cond1 = cond11 and cond12
        cond21 = (
            new_min_x >= min_x
            and new_min_y >= min_y
            and new_max_x <= max_x
            and new_max_y <= max_y
        )
        if not (cond1 or cond21):
            continue
        text_anc_token = token.layout.text_anchor.text_segments
        si, ei = text_anc_token[0].start_index, text_anc_token[0].end_index
        orig_temp_text = orig_invoice_json.text[si:ei].strip().lower()
        mapping_text_stripped = mapping_text.strip().lower()
        if orig_temp_text in mapping_text_stripped:
            for t3 in list(mapping_list):
                ratio = fuzz.ratio(t3.lower(), orig_temp_text)
                if ratio > 75:
                    mapping_list.remove(t3)
                    match_string_pair.append([t3, orig_temp_text])
                    text_anc_tokens.extend(text_anc_token)
                    page_anc["x"].extend([new_min_x, new_max_x])
                    page_anc["y"].extend([new_min_y, new_max_y])
                    confidence.append(0.9)
    sorted_temp_token = sorted(text_anc_tokens, key=lambda x: x.end_index)
    temp_mention_text = ""
    for index, seg in enumerate(sorted_temp_token):
        si = seg.start_index
        ei = seg.end_index
        ent_text = orig_invoice_json.text[si:ei]
        cond1 = index in [0, len(sorted_temp_token)]
        cond2 = ent_text.strip() in [")", "(", ":", " ", "/", "\\"]
        if cond1 and cond2:
            continue
        temp_mention_text += ent_text
    try:
        updated_page_anc = {
            "min_x": min(page_anc["x"]),
            "min_y": min(page_anc["y"]),
            "max_x": max(page_anc["x"]),
            "max_y": max(page_anc["y"]),
        }
    except ValueError:
        # recheck the format
        updated_page_anc = {
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
        }
        temp_mention_text = mapping_text
        method = "OCR-TU-Direct"
    # This sorted_temp_token(list(text_segment-object)) is list(text_segments[0]...(>1))
    updated_text_anc = {"textSegments": sorted_temp_token}
    return (
        updated_page_anc,
        updated_text_anc,
        temp_mention_text,
        match_string_pair,
        method,
    )


def get_token(
    json_dict: documentai.Document,
    page: int,
    text_anchors_check: MutableSequence[documentai.Document.TextAnchor.TextSegment],
) -> Tuple[Union[Dict[str, float], None], Any,]:
    """
    This function takes a loaded JSON, page number, and text anchors as input
    and returns the text anchors and page anchors.
    Args:
        json_dict (documentai.Document): The loaded JSON document.
        page (int): The page number.
        text_anchors_check (MutableSequence[documentai.Document.TextAnchor.TextSegment]):
            List of text anchors to check.
    Returns:
        Tuple[
            Union[Dict[str, float], None],
            Union[MutableSequence[documentai.Document.TextAnchor.TextSegment], None]
        ]
            - A tuple containing the final page anchors, text anchors, and confidence.
    """
    temp_text_anc = []
    temp_confidence = []
    temp_ver: Dict[str, List[float]] = {"x": [], "y": []}
    ta_si = text_anchors_check[0].start_index
    ta_ei = text_anchors_check[0].end_index
    for token in json_dict.pages[page].tokens:
        text_segs = token.layout.text_anchor.text_segments
        si = text_segs[0].start_index
        ei = text_segs[0].end_index
        if text_segs == text_anchors_check:
            text_temp = json_dict.text[si:ei]
            cond2 = "\n" not in text_temp and len(text_temp) <= 2
            if len(text_temp) > 2 or cond2:
                norm_verts = token.layout.bounding_poly.normalized_vertices
                min_x, max_x, min_y, max_y = get_min_max_x_y(norm_verts)
                temp_text_anc = text_segs
        elif si >= ta_si - 2 and ei <= ta_ei + 2:
            text_temp = json_dict.text[si:ei]
            if len(text_temp) > 2 or "\n" not in text_temp:
                norm_verts = token.layout.bounding_poly.normalized_vertices
                min_x, max_x, min_y, max_y = get_min_max_x_y(norm_verts)
                temp_ver["x"].extend([min_x, max_x])
                temp_ver["y"].extend([min_y, max_y])
                text_anc_token = text_segs
                for an1 in text_anc_token:
                    temp_text_anc.append(an1)
                temp_confidence.append(token.layout.confidence)
    if not temp_text_anc:
        for token in json_dict.pages[page].tokens:
            text_segs = token.layout.text_anchor.text_segments
            ts_si = text_segs[0].start_index
            ts_ei = text_segs[0].end_index
            if abs(ts_si - ta_si) <= 2:
                text_temp = json_dict.text[ts_si:ts_ei]
                if len(text_temp) > 2 or "\n" not in text_temp:
                    norm_verts = token.layout.bounding_poly.normalized_vertices
                    min_x, max_x, min_y, max_y = get_min_max_x_y(norm_verts)
                    temp_text_anc = text_segs
    if temp_text_anc and temp_ver["x"]:
        final_ver = {
            "min_x": min(temp_ver["x"]),
            "min_y": min(temp_ver["y"]),
            "max_x": max(temp_ver["x"]),
            "max_y": max(temp_ver["y"]),
        }
        final_text_anc = sorted(temp_text_anc, key=lambda x: x.end_index)
        return final_ver, final_text_anc
    # else:
    return None, None


def get_updated_entity(
    entity: documentai.Document.Entity,
    orig_invoice_json: documentai.Document,
    translation_api_output: List[Dict[str, str]],
    english_page_num: int,
    diff_y: float = 0.05,
    diff_x: float = 0.3,
) -> Tuple[Dict[str, Any], List[Any], str, List[List[str]], str, List[Dict[str, str]],]:
    """
    Function maps the entity from source to target and gives the back mapped entity.
    Args:
        entity (documentai.Document.Entity): Document AI extracted entity dictionary.
        orig_invoice_json (documentai.Document): Original document Invoice processor json output.
        translation_api_output (List[Dict[str, str]]):
            Mapping dictionary of source and corresponding translated text.
        english_page_num (int): Document page number.
        diff_y (float): Y-coordinate offset.
        diff_x (float): X-coordinate offset.
    Returns:
        Tuple[
            Dict[str, Any],
            List[Any],
            str, List[List[str]], str,List[Dict[str, str]]
        ]
            - main_page_anc (Dict[str, List[float]]):
                Dictionary containing min-max x&y coordinates of the mapped entity.
            - main_text_anc (MutableSequence[documentai.Document.TextAnchor.TextSegment]):
                List of start and end indexes of the mapped entity.
            - main_mentiontext (str): Mapped entity text.
            - unique_list (List[List[str]]): Unique list of matched string pairs.
            - method (str): Based on mapping block.
            - mapping_text_list (List[Dict[str, str]]]):
                List of matched translation units with entity text.
    """
    # Get matched translated text units
    mapping_text_list = find_matched_translation_pairs(entity, translation_api_output)
    main_mentiontext = ""
    main_text_anc = []
    main_page_anc1: Dict[str, List[float]] = {"x": [], "y": []}
    english_bb_area = entity.page_anchor.page_refs[0].bounding_poly.normalized_vertices
    min_max_x_y = get_min_max_x_y(english_bb_area)
    updated_page_anc: Dict[str, float] = {}
    method = ""
    mentiontext = ""
    match_str_pair: List[Any] = []
    # Iterate over matched pairs {source: other lang, target: english}.
    for map_text in mapping_text_list:
        (
            updated_page_anc,
            updated_text_anc,
            mentiontext,
            match_str_pair,
            method,
        ) = get_page_text_anc_mentiontext(
            entity,
            orig_invoice_json,
            min_max_x_y,
            map_text["sourceText"],
            diff_y,
            diff_x,
            english_page_num,
        )
        if len(updated_page_anc) == 0:
            (
                updated_page_anc,
                updated_text_anc,
                mentiontext,
                match_str_pair,
                method,
            ) = updated_entity_secondary(
                orig_invoice_json,
                min_max_x_y,
                map_text["sourceText"],
                english_page_num,
            )
        if updated_page_anc:
            main_page_anc1["x"].extend(
                [updated_page_anc["min_x"], updated_page_anc["max_x"]]
            )
            main_page_anc1["y"].extend(
                [updated_page_anc["min_y"], updated_page_anc["max_y"]]
            )
            for text_anc in updated_text_anc["textSegments"]:
                if text_anc not in main_text_anc:
                    main_text_anc.append(text_anc)
    main_text_anc = sorted(main_text_anc, key=lambda x: x.end_index)
    if main_text_anc:
        for index, text_an1 in enumerate(main_text_anc):
            si = text_an1.start_index
            ei = text_an1.end_index
            ent_text = orig_invoice_json.text[si:ei]
            # remove unwanted chars
            cond1 = index in [0, len(main_text_anc) - 1]
            punctuations = [")", "(", ":", " ", "/", "\\"]
            if cond1 and ent_text.strip() in punctuations:
                continue
            main_mentiontext += ent_text
    else:
        main_mentiontext = mentiontext
    unique_list = []
    for item in match_str_pair:
        if item not in unique_list:
            unique_list.append(item)
    main_page_anc2 = {
        "min_x": min(main_page_anc1["x"]),
        "min_y": min(main_page_anc1["y"]),
        "max_x": max(main_page_anc1["x"]),
        "max_y": max(main_page_anc1["y"]),
    }
    text_anchor = documentai.Document.TextAnchor()
    text_anchor.text_segments = main_text_anc
    return (
        main_page_anc2,
        text_anchor.text_segments,
        main_mentiontext,
        unique_list,
        method,
        mapping_text_list,
    )


def find_substring_indexes(
    text: str, substring: str
) -> Tuple[List[Tuple[int, int]], List[List[str]]]:
    """
    Function returns the start and end indexes of all the matches
    between ocr text and mapping/mention text.
    Args:
        text (str): DocAI OCR text output.
        substring (str): Translation API mapping text/DocAI entity mentioned text.
    Returns:
        Tuple[List[Tuple[int, int]], List[List[str]]]
            - matches  (List[Tuple[int, int]]): List of start and end indexes of all the matches.
            - match_string_pair (List[List[str]]): List of pair of matched strings.
    """
    substring = substring.replace(",", ".")
    list_str = substring.strip().split()
    matches = []
    text_1 = text.replace(",", ".").lower()
    match_string_pair = []
    if len(list_str) == 1:
        list_str_1 = list_str[0].replace(",", ".")
        pattern = re.compile(re.escape(list_str_1), re.IGNORECASE)
        for match in pattern.finditer(text_1):
            si = match.start()
            ei = match.end()
            ratio = fuzz.ratio(substring, text[si:ei])
            if ratio > 0.8:
                matches.append((si, ei))
                match_string_pair.append([substring, text[si:ei]])
    else:
        part = f"{re.escape(substring.strip())}"
        pattern = re.compile(part, re.IGNORECASE)
        # remove new line if present
        text1 = text_1.replace("\n", " ").strip()
        for match in pattern.finditer(text_1):
            si = match.start()
            ei = match.end()
            delta = abs(ei - si)
            cond1 = delta <= len(substring) + 15
            cond2 = delta >= abs(len(substring) * 0.75)
            if cond1 and cond2:
                ratio = fuzz.ratio(substring, text1[si:ei])
                if ratio > 0.8:
                    matches.append((si, ei))
                    match_string_pair.append([substring, text1[si:ei]])
    return matches, match_string_pair


def translation_text_units(
    project_id: str,
    location: str,
    processor_version: str,
    processor_id: str,
    target_language: str,
    source_language: str,
    input_uri: str,
    output_gcs_bucket: str,
    output_gcs_prefix: str,
    save_translated_doc: Optional[bool] = False,
    is_native: Optional[bool] = False,
    remove_shadow: Optional[bool] = True,
) -> Tuple[bytes, List[Dict[str, str]], Dict[str, Any]]:
    """
    Function to translate the document from source to target language.
    Args:
        project_id (str): GCP project id.
        location (str): Location of the docai processor.
        processor_version (str): DocAI processor version.
        processor_id (str): DocAI processor id.
        target_language (str): Language to which document is to be translated.
        source_language (str): Document source language.
        input_uri (str): GCS Document URI.
        output_gcs_bucket (str): GCS bucket name.
        output_gcs_prefix (str): GCS prefix where to store the file.
        save_translated_doc (bool, optional): True, to save the translated doc. Defaults to False.
        is_native (bool, optional): True, if input doc is native. Defaults to False.
        remove_shadow (bool, optional):
            True, to remove the shadow text from translated doc. Defaults to True.
    Returns:
        Tuple[bytes, List[Dict[str, str]], Dict[str, Any]]: A tuple containing
            - pdf_bytes: Bytes of the translated document.
            - doc_text_units: Mapping dictionary of source and corresponding translated text.
            - json_response: Translated API json response.
    """
    # Translation API.
    url = (
        f"https://translate.googleapis.com/v3/projects/{project_id}"
        f"/locations/global:translateDocument"
    )
    headers = {
        "content-type": "application/json",
        "Authorization": f"Bearer {get_access_token()}",
    }
    # request-module is the only way and also users need to raise a request
    # to enable this feature(output_text_unit) in their project
    json_obj = {
        "source_language_code": source_language,
        "target_language_code": target_language,
        "document_input_config": {"gcs_source": {"input_uri": input_uri}},
        "output_text_unit": "True",
        "is_translate_native_pdf_only": is_native,
        "enable_shadow_removal_native_pdf": remove_shadow,
    }
    x = requests.post(url, json=json_obj, headers=headers, timeout=300)
    if x.status_code != 200:
        print(f"\tstatus_code: {x.status_code}, reason: {x.reason}")
    json_response = x.json()
    doc_trans = json_response["documentTranslation"]
    pdf_bytes = base64.b64decode(doc_trans["byteStreamOutputs"][0])
    redacted_pdf_bytes = redact(
        project_id, location, processor_version, processor_id, pdf_bytes
    )
    if save_translated_doc:
        # save translated document
        filename = input_uri.split("/")[-1]
        upload_to_cloud_storage(
            filename,
            redacted_pdf_bytes,
            output_gcs_bucket,
            os.path.join(output_gcs_prefix, "translated_pdfs"),
        )
    doc_text_units = doc_trans["textUnits"]
    return redacted_pdf_bytes, doc_text_units, json_response


def run_consolidate(
    english_invoice_doc: documentai.Document,
    orig_invoice_doc: documentai.Document,
    translation_api_output: List[Dict[str, str]],
    diff_x: float,
    diff_y: float,
    lang: str,
) -> Tuple[pd.DataFrame, documentai.Document]:
    """
    This function takes the source, target parsed jsons, and text units as input
    and gives an updated json and comparison dataframe as output.
    Args:
        english_invoice_json (documentai.Document):
            JSON output from DocAI Invoice parser when translated.
        orig_invoice_json (documentai.Document):
            JSON output from DocAI Invoice parser for the target language.
        translation_api_output (List[Dict[str, str]]): Text units (sourceText, targetText pairs).
        diff_y: Y-coordinate offset.
        diff_x: X-coordinate offset.
        lang: Original document language.
    Returns:
        Tuple[pd.DataFrame, documentai.Document] :
            - df (pd.DataFrame): Comparison dataframe.
            - orig_invoice_json (documentai.Document): Updated Original invoice JSON.
    """
    _updated_entities = []
    updated_text_anchor: List[Any] = []
    df = pd.DataFrame(
        columns=[
            "English_entity_type",
            "English_entity_MT",
            "Original_entity_MT",
            "match_pair",
            "method",
            "map_text_list",
            "English_entity_bbox",
            "Original_entity_bbox",
            "Language",
        ]
    )
    for _entity in english_invoice_doc.entities:
        # Error handling: no pageanchor for entity
        if not _entity.page_anchor:
            print("************")
            continue
        english_page_num = int(_entity.page_anchor.page_refs[0].page)
        try:
            if not _entity.properties:
                ent_eng_type = _entity.type_
                ent_eng_mt = _entity.mention_text
                pgrfs = _entity.page_anchor.page_refs[0]
                bounding_box = pgrfs.bounding_poly.normalized_vertices
                ent_eng_bbox = get_min_max_x_y(bounding_box)
                (
                    updated_page_anchor,
                    updated_text_anchor,
                    mentiontext,
                    match_str_pair,
                    method,
                    map_text_list,
                ) = get_updated_entity(
                    _entity,
                    orig_invoice_doc,
                    translation_api_output,
                    english_page_num,
                    diff_y,
                    diff_x,
                )
                nvs = get_normalized_vertices(updated_page_anchor)
                _bounding_poly = documentai.BoundingPoly(normalized_vertices=nvs)
                _entity.confidence = 1
                _entity.mention_text = mentiontext
                page_refs = documentai.Document.PageAnchor.PageRef(
                    page=english_page_num, bounding_poly=_bounding_poly
                )
                _entity.page_anchor = documentai.Document.PageAnchor(
                    page_refs=[page_refs]
                )
                _ts = updated_text_anchor[0]
                _entity.text_anchor.text_segments = [_ts]
                _entity.text_anchor.content = mentiontext
                if _entity.normalized_value:
                    del _entity.normalized_value
                _updated_entities.append(_entity)
                df.loc[len(df.index)] = [
                    ent_eng_type,
                    ent_eng_mt.strip("\n"),
                    mentiontext.strip("\n"),
                    match_str_pair,
                    method,
                    map_text_list,
                    ent_eng_bbox,
                    [
                        updated_page_anchor["min_x"],
                        updated_page_anchor["min_y"],
                        updated_page_anchor["max_x"],
                        updated_page_anchor["max_y"],
                    ],
                    lang,
                ]
            else:
                _child_properties = []
                _parent_text_segments = []
                _parent_x_y: Dict[str, List[Any]] = {"x": [], "y": []}
                for _child_ent in _entity.properties:
                    child_ent_eng_type = _child_ent.type_
                    child_ent_eng_mt = _child_ent.mention_text
                    pgrfs = _child_ent.page_anchor.page_refs[0]
                    bounding_box_1 = pgrfs.bounding_poly.normalized_vertices
                    child_ent_eng_bbox = get_min_max_x_y(bounding_box_1)
                    try:
                        try:
                            (
                                updated_page_anchor,
                                updated_text_anchor,
                                mentiontext,
                                match_str_pair,
                                method,
                                map_text_list,
                            ) = get_updated_entity(
                                _child_ent,
                                orig_invoice_doc,
                                translation_api_output,
                                english_page_num,
                                0.01,
                                0.1,
                            )
                        except ValueError:
                            (
                                updated_page_anchor,
                                updated_text_anchor,
                                mentiontext,
                                match_str_pair,
                                method,
                                map_text_list,
                            ) = get_updated_entity(
                                _child_ent,
                                orig_invoice_doc,
                                translation_api_output,
                                english_page_num,
                                diff_y,
                                diff_x,
                            )
                        nvs = get_normalized_vertices(updated_page_anchor)
                        _bounding_poly = documentai.BoundingPoly(
                            normalized_vertices=nvs
                        )
                        page_refs = documentai.Document.PageAnchor.PageRef(
                            page=english_page_num, bounding_poly=_bounding_poly
                        )
                        _pa = documentai.Document.PageAnchor(page_refs=[page_refs])
                        _child_property = documentai.Document.Entity(
                            confidence=1,
                            mention_text=mentiontext,
                            type_=_child_ent.type_,
                            page_anchor=_pa,
                        )
                        _child_ent.text_anchor.content = mentiontext
                        if _child_ent.normalized_value:
                            del _child_ent.normalized_value
                        _child_properties.append(_child_property)
                        _updated_text_anchor = updated_text_anchor[0]
                        _parent_text_segments.extend([_updated_text_anchor])
                        for norm_ver in _bounding_poly.normalized_vertices:
                            _parent_x_y["x"].append(norm_ver.x)
                            _parent_x_y["y"].append(norm_ver.y)
                        df.loc[len(df.index)] = [
                            child_ent_eng_type,
                            child_ent_eng_mt.strip("\n"),
                            mentiontext.strip("\n"),
                            match_str_pair,
                            method,
                            map_text_list,
                            child_ent_eng_bbox,
                            [
                                updated_page_anchor["min_x"],
                                updated_page_anchor["min_y"],
                                updated_page_anchor["max_x"],
                                updated_page_anchor["max_y"],
                            ],
                            lang,
                        ]
                    except ValueError:
                        df.loc[len(df.index)] = [
                            child_ent_eng_type,
                            child_ent_eng_mt.strip("\n"),
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            lang,
                        ]
                _sorted_parent_text_segments = sorted(
                    _parent_text_segments, key=lambda x: int(x.end_index)
                )
                _parent_mention_text = ""
                for ts in _sorted_parent_text_segments:
                    si = ts.start_index
                    ei = ts.end_index
                    temp = orig_invoice_doc.text[si:ei]
                    _parent_mention_text += f" {temp}"
                parent_page_anchor = {
                    "min_x": min(_parent_x_y["x"]),
                    "min_y": min(_parent_x_y["y"]),
                    "max_x": max(_parent_x_y["x"]),
                    "max_y": max(_parent_x_y["y"]),
                }
                nvs = get_normalized_vertices(parent_page_anchor)
                _parent_bounding_poly = documentai.BoundingPoly(normalized_vertices=nvs)
                page_refs = documentai.Document.PageAnchor.PageRef(
                    page=english_page_num, bounding_poly=_parent_bounding_poly
                )
                _pa = documentai.Document.PageAnchor(page_refs=[page_refs])
                _parent_entity = documentai.Document.Entity(
                    confidence=1,
                    id=_entity.id,
                    type_=_entity.type_,
                    mention_text=_parent_mention_text,
                    properties=_child_properties,
                    page_anchor=_pa,
                )
                _ts = updated_text_anchor[0]
                _parent_entity.text_anchor.text_segments = [_ts]
                _updated_entities.append(_parent_entity)
        except (IndexError, ValueError):
            ent_t = _entity.type_
            ent_mt = _entity.mention_text
            ent_eng_bbox12: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
            pgrfs = _entity.page_anchor.page_refs[0]
            bounding_box = pgrfs.bounding_poly.normalized_vertices
            if bounding_box:
                ent_eng_bbox12 = get_min_max_x_y(bounding_box)
            df.loc[len(df.index)] = [
                ent_t,
                ent_mt.strip("\n"),
                "",
                "",
                "",
                "",
                ent_eng_bbox12,
                "",
                lang,
            ]
    for index, entity in enumerate(_updated_entities):
        entity.id = str(index)
        if entity.properties:
            for child_index, child_entity in enumerate(entity.properties):
                child_entity.id = str(child_index)
    orig_invoice_doc.entities = _updated_entities
    return df, orig_invoice_doc
