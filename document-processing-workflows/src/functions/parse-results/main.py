# flake8: noqa: E501
# Copyright 2023 Google LLC
# SPDX-License-Identifier: Apache-2.0

import gc
import json
import mimetypes
import shutil
import tempfile
import base64
from pathlib import Path
from typing import Dict, List

import functions_framework
import pypdfium2 as pdfium
from PIL import Image
import psutil
from flask import jsonify
from google.cloud import storage


@functions_framework.http
def parse_results(request):
    """Triggered by Workflow.
    Args:
        request (flask.Request): The request object.
        <https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data>
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`
        <https://flask.palletsprojects.com/en/1.1.x/api/#flask.make_response>.
    """
    request_json = request.get_json(silent=True)
    response = request_json
    print(request_json)
    if not request_json:
        raise ValueError("Request JSON is empty")
    if "inputBucket" not in request_json:
        raise ValueError("inputBucket is not included in request_json")
    if "inputObject" not in request_json:
        raise ValueError("inputObject is not included in request_json")
    if "resultBucket" not in request_json:
        raise ValueError("resultBucket is not included in request_json")
    if "resultPrefix" not in request_json:
        raise ValueError("resultPrefix is not included in request_json")

    input_bucket_name = request_json.get("inputBucket")
    input_object_name = request_json.get("inputObject")
    result_bucket_name = request_json.get("resultBucket")
    result_prefix = request_json.get("resultPrefix")
    # define pageImageUrlPrefix and pageImageNames which may be used by a frontend to render the document pages from images stored on GCS
    response["pageImageUrlPrefix"] = result_prefix
    response["pageImageNames"] = []
    # retrieve all blobs in the result bucket for the given result prefix (e.g. belonging to the same batchProcess output)
    blobs = list_results(result_bucket_name, result_prefix)
    # only use blobs of content-type application/json which contain batchProcess output
    blobs = [blob for blob in blobs if blob.content_type == "application/json"]
    # if the result JSON is sharded merge it into a single result JSON
    if len(blobs) > 1:
        # merge sharded results
        document, page_image_names = merge_sharded_results(
            blobs,
            input_bucket_name,
            input_object_name,
            result_bucket_name,
            result_prefix,
        )
        # add pageImageNames from shards to response
        response["pageImageNames"] = response["pageImageNames"] + page_image_names
        # upload unsharded document
        storage_client = storage.Client()
        process_result_bucket = storage_client.get_bucket(result_bucket_name)
        document_blob = storage.Blob(
            name=str(Path(result_prefix, "unsharded.json")),
            bucket=process_result_bucket,
        )
        document_blob.upload_from_string(
            json.dumps(document), content_type="application/json"
        )
        # update resultObject to unsharded blob in response
        response["resultObject"] = document_blob.name
        # delete shard blobs
        for blob in blobs:
            blob.delete()
    else:  # document not sharded
        blob = blobs[0]
        # download blob content and parse into JSON
        content = blob.download_as_bytes()
        document = json.loads(content)
        # set resultObject to blob name in response
        response["resultObject"] = blob.name
        if (
            "pages" not in document
            or len(document["pages"]) == 0
            or "image" not in document["pages"][0]
        ):
            # if the pages property is missing (usually for CDS) then we need to render the images from PDF output and put them in the same location as the batchProcess output
            response["pageImageNames"] = response[
                "pageImageNames"
            ] + render_pdf_to_image(
                input_bucket_name=input_bucket_name,
                input_object_name=input_object_name,
                result_bucket_name=result_bucket_name,
                result_prefix=result_prefix,
            )
        else:
            # extract images from batchProcess output and put them into the same location as the batchProcess output for better performance in the HITL UI
            response["pageImageNames"] = response["pageImageNames"] + extract_image(
                document,
                input_bucket_name,
                input_object_name,
                result_bucket_name,
                result_prefix,
            )
            # remove images from pages
            for page in document["pages"]:
                if "image" in page:
                    del page["image"]
            # upload modified document
            blob.upload_from_string(
                json.dumps(document), content_type="application/json"
            )

    if "pages" in document:
        page_count = len(document["pages"])
    else:
        # splitter result may not have pages, only entities so we need to find the highest page number from the entities
        page_count = 1
        if "entities" in document:
            for entity in document["entities"]:
                if "pageAnchor" in entity and "pageRefs" in entity["pageAnchor"]:
                    for page_anchor in entity["pageAnchor"]["pageRefs"]:
                        if "page" in page_anchor:
                            # page_anchor starts at page 0
                            page_count = max(page_count, int(page_anchor["page"]) + 1)
    response["pageCount"] = page_count
    print(response)
    return jsonify(response)


def check_entity_confidence(entities, entity_labels):
    hitl = False
    for entity in entities:
        entity_label = [
            entity_label
            for entity_label in entity_labels
            if entity_label.label == entity.type
        ]
        if entity.get("confidence", 0) <= entity_label.threshold:
            hitl = True
            # mark entity as review pending
            entity["prediction"] = {"status": "pending"}
    return entities, hitl


def apply_text_offset(json_input, text_offset):
    lookup_key = "textSegments"
    if isinstance(json_input, dict):
        for k, v in json_input.items():
            if k == lookup_key:
                for text_segment in v:
                    if "startIndex" in text_segment:
                        text_segment["startIndex"] = str(
                            int(text_segment["startIndex"]) + text_offset
                        )
                    if "endIndex" in text_segment:
                        text_segment["endIndex"] = str(
                            int(text_segment["endIndex"]) + text_offset
                        )
            else:
                apply_text_offset(v, text_offset)
    elif isinstance(json_input, list):
        for item in json_input:
            apply_text_offset(item, text_offset)


def merge_sharded_results(
    blobs: List[storage.Blob],
    input_bucket_name,
    input_object_name,
    result_bucket_name,
    result_prefix,
):
    shard_count = len(blobs)
    print(f"Merging {len(blobs)} sharded results")
    merged_document: Dict = {}
    page_image_names_per_shard: List[str] = [""] * shard_count
    text_offset = 0
    shard_index = next_shard_index = 0
    text = [""] * shard_count
    for blob in blobs:
        print(f"Downloading content of blob {blob.name}")
        content = blob.download_as_bytes()
        document = json.loads(content)
        del content
        print("Extracting images to external files or render from input document")
        # page_offset is the minimum of the pageNumbers of the current shard but starts at 0 - thus substracting 1
        page_offset = min(int(page["pageNumber"]) for page in document["pages"]) - 1
        if "shardInfo" in document:
            shard_info = document["shardInfo"]
            if "textOffset" in shard_info:
                text_offset = int(shard_info["textOffset"])
            if "shardCount" in shard_info:
                if shard_count != int(shard_info["shardCount"]):
                    raise ValueError(
                        f"Shard count mismatch! Current shard_count is {shard_count} shardInfo has {shard_info['shardCount']} and there are {len(blobs)} blobs with shard information"
                    )
            if "shardIndex" in shard_info:
                shard_index = int(shard_info["shardIndex"])
                if shard_index >= shard_count:
                    raise ValueError(
                        f"Shard index {shard_index} larger than or equal to shard count {shard_count}"
                    )
            else:
                # auto increment shard_index by one - only works if blobs are in the same order as shard index, which they usually are but not guaranteed
                next_shard_index = shard_index + 1
            del document["shardInfo"]
        print(f"Working on shard_index {shard_index} out of {shard_count} total shards")
        print("Extracting images from current shard")
        page_image_names_per_shard[shard_index] = extract_image(
            document,
            input_bucket_name,
            input_object_name,
            result_bucket_name,
            result_prefix,
            page_offset,
        )
        print("Remove images from document JSON")
        for page in document.get("pages", []):
            if "image" in page:
                del page["image"]
        print("Applying page offset to all pageRefs")
        for entity in document.get("entities", []):
            page_anchor = entity.get("pageAnchor")
            if page_anchor:
                page_refs = page_anchor.get("pageRefs")
                if page_refs:
                    for page_ref in page_refs:
                        page = page_ref.get("page")
                        if page:
                            page_ref["page"] = int(page) + page_offset
                        else:
                            page_ref["page"] = page_offset
        print("Applying text offset to all text segments")
        apply_text_offset(document, text_offset)
        print("Merging document into merged_document")
        for key in document.keys():
            if isinstance(document[key], list):
                if key in merged_document:
                    merged_document[key] = merged_document[key] + document[key]
                else:
                    merged_document[key] = document[key]
            elif key == "text":
                text[shard_index] = document[key]
            else:
                if key not in merged_document:
                    merged_document[key] = document[key]
        del document
        gc.collect()
        print("Memory: ", psutil.virtual_memory())
        shard_index = next_shard_index
    # flatten page_image_names_per_shard
    page_image_names = [
        item for sub_list in page_image_names_per_shard if sub_list for item in sub_list
    ]
    # join all text entries in the right order
    merged_document["text"] = "".join(text)
    return merged_document, page_image_names


def list_results(bucket_name: str, prefix: str) -> List[storage.Blob]:
    """Get list of blobs from GCS

    Args:
        bucket_name (str): GCS Bucket of processor output
        prefix (str): GCS prefix where processor output blobs are located

    Returns:
        blobs (list[storage.Blob]): list of blobs with processor result
    """
    print(
        f"Retrieving blobs with processor results from bucket {bucket_name} with prefix {prefix}"
    )
    storage_client = storage.Client()
    # ensure that prefix ends with a /
    prefix = prefix.rstrip("/") + "/"
    blobs = storage_client.list_blobs(bucket_name, prefix=prefix)
    return list(blobs)


def render_pdf_to_image(
    input_bucket_name,
    input_object_name,
    result_bucket_name,
    result_prefix,
    page_offset=None,
):
    page_image_names = []
    # create a temp folder based on temp_local_filename
    # use ghostscript to export the pdf into pages as pngs in the temp dir
    tempdir = tempfile.mkdtemp()
    _, input_file = tempfile.mkstemp(dir=tempdir)
    storage_client = storage.Client()
    input_bucket = storage_client.get_bucket(input_bucket_name)
    input_object = input_bucket.get_blob(input_object_name)
    input_object.download_to_filename(input_file)
    # render images using pypdfium2
    pdf = pdfium.PdfDocument(input_file)
    n_pages = len(pdf)
    page_indices = [i for i in range(n_pages)]
    renderer = pdf.render(
        pdfium.PdfBitmap.to_pil,
        page_indices=page_indices,
        scale=150 / 72,  # 150dpi resolution
    )
    if page_offset is None:
        page_offset = 0
    for i, image in zip(page_indices, renderer):
        page_number = i + page_offset + 1
        png_file_name = str(Path(tempdir, f"page-{page_number:04d}.png"))
        jpg_file_name = str(Path(tempdir, f"page-{page_number:04d}.jpg"))
        image.thumbnail((1500, 1500), Image.LANCZOS)
        print(f"Saving page {page_number}")
        image.save(png_file_name)
        image.save(jpg_file_name, optimize=True, quality=95)
        # compare filesize between png and jpg and only upload the smaller file
        if Path(png_file_name).stat().st_size < Path(jpg_file_name).stat().st_size:
            image_filename = png_file_name
            content_type = "image/png"
            Path(jpg_file_name).unlink()
        else:
            image_filename = jpg_file_name
            content_type = "image/jpg"
            Path(png_file_name).unlink()
        page_image_names.append(Path(image_filename).name)
        image_blob_uri = (
            f"gs://{result_bucket_name}/{Path(result_prefix,Path(image_filename).name)}"
        )
        image_blob = storage.Blob.from_string(uri=image_blob_uri, client=storage_client)
        image_blob.cache_control = "private,max-age=604800"
        print(f"Uploading file {image_filename} to {image_blob_uri}")
        image_blob.upload_from_filename(image_filename, content_type=content_type)
    print("Deleting temporary directory")
    shutil.rmtree(tempdir, ignore_errors=True)
    return page_image_names


def extract_image(
    document,
    input_bucket_name,
    input_object_name,
    result_bucket_name,
    result_prefix,
    page_offset=0,
):
    page_image_names = []
    for page in document["pages"]:
        if "image" in page and "content" in page["image"]:
            if "mimeType" in page["image"]:
                extension = mimetypes.guess_extension(page["image"]["mimeType"])
            else:
                extension = ".png"
            storage_client = storage.Client()
            image_filename = f"page-{int(page['pageNumber']):03d}{extension}"
            page_image_names.append(image_filename)
            page_blob_url = f"gs://{result_bucket_name}/{Path(result_prefix,Path(image_filename).name)}"
            page_blob = storage.Blob.from_string(
                uri=page_blob_url, client=storage_client
            )
            page_blob.cache_control = "private,max-age=604800"
            page_blob.upload_from_string(
                base64.b64decode(page["image"]["content"]),
                content_type=mimetypes.types_map[extension],
            )
        else:
            page_image_names = page_image_names + render_pdf_to_image(
                input_bucket_name=input_bucket_name,
                input_object_name=input_object_name,
                result_bucket_name=result_bucket_name,
                result_prefix=result_prefix,
                page_offset=page_offset,
            )
    return page_image_names
