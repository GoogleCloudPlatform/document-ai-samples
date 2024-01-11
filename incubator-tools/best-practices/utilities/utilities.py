"""This script offers a suite of utility functions designed to simplify
and streamline operations associated with Google Cloud Storage (GCS) and
Google Cloud's DocumentAI."""

# Import the libraries
import difflib
import io
import json
import operator
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1beta3 as documentai
from google.cloud import storage
from google.cloud.exceptions import Conflict
from google.cloud.exceptions import NotFound
from pandas import DataFrame
import pandas as pd
from PIL import Image

pd.options.mode.chained_assignment = None  # default='warn'


def file_names(gs_file_path: str) -> Tuple[List[str], Dict[str, str]]:
    """
    Retrieves the list of files from a given Google Cloud Storage path.

    Args:
        gs_file_path (str): The Google Cloud Storage path in the format
        "gs://<bucket-name>/<folder-path>/".

    Returns:
        tuple: A tuple containing two elements:
            1. List of filenames present in the specified path.
            2. Dictionary with filenames as keys and
            their respective full paths in the bucket as values.
    """

    bucket = gs_file_path.split("/")[2]
    file_names_list = []
    file_dict = {}

    storage_client = storage.Client()
    source_bucket = storage_client.get_bucket(bucket)

    filenames = [
        filename.name
        for filename in list(
            source_bucket.list_blobs(prefix=(("/").join(gs_file_path.split("/")[3:])))
        )
    ]

    for i, _ in enumerate(filenames):
        x = filenames[i].split("/")[-1]
        if x:
            file_names_list.append(x)
            file_dict[x] = filenames[i]

    return file_names_list, file_dict


def check_create_bucket(bucket_name: str) -> storage.bucket.Bucket:
    """
    Checks if a specified Google Cloud Storage bucket exists. If not, it creates one.
    Primarily used for creating a temporary bucket to store processed files.

    Args:
        bucket_name (str): The name of the bucket to check or create.

    Returns:
        google.cloud.storage.bucket.Bucket:
        The bucket object corresponding to the provided bucket name.
    """

    storage_client = storage.Client()
    try:
        bucket = storage_client.get_bucket(bucket_name)
        print(f"Bucket {bucket_name} already exists.")
    except NotFound:
        bucket = storage_client.create_bucket(bucket_name)
        print(f"Bucket {bucket_name} created.")

    return bucket


def bucket_delete(bucket_name: str) -> None:
    """
    Deletes a specified Google Cloud Storage bucket.
    Primarily used for deleting temporary buckets after their purpose is served.

    Args:
        bucket_name (str): The name of the bucket to be deleted.

    Returns:
        None. If the bucket exists, it will be deleted.
        If it doesn't exist or an error occurs,
        the function will silently pass.
    """

    print("Deleting bucket:", bucket_name)

    storage_client = storage.Client()
    try:
        bucket = storage_client.get_bucket(bucket_name)
        bucket.delete(force=True)
    except (NotFound, Conflict):
        pass


def list_blobs(bucket_name: str) -> List[str]:
    """
    Retrieves a list of filenames (blobs) from a specified Google Cloud Storage bucket.

    Args:
        bucket_name (str): The name of the bucket from which to retrieve the list of filenames.

    Returns:
        list: A list containing the names of all files (blobs) present in the specified bucket.
    """

    blob_list = []
    storage_client = storage.Client()
    blobs = storage_client.list_blobs(bucket_name)

    for blob in blobs:
        blob_list.append(blob.name)

    return blob_list


def matching_files_two_buckets(
    bucket_1: str, bucket_2: str
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Compares the files from two Google Cloud Storage buckets to find files with similar names.

    Args:
        bucket_1 (str): Name of the first GCS bucket.
        bucket_2 (str): Name of the second GCS bucket.

    Returns:
        tuple: A tuple containing two dictionaries:
            1. matched_files_dict: Dictionary with filenames from
            bucket_1 as keys and corresponding similar filenames
            from bucket_2 as values.
            2. non_matched_files_dict: Dictionary with filenames from
            bucket_1 as keys and a message indicating no similar file
            was found in bucket_2 as values.
    """

    bucket_1_blobs = list_blobs(bucket_1)
    bucket_2_blobs = list_blobs(bucket_2)

    matched_files_dict = {}
    non_matched_files_dict = {}

    for i in bucket_1_blobs:
        for j in bucket_2_blobs:
            matched_score = difflib.SequenceMatcher(None, i, j).ratio()

            print("matched_score:", matched_score)
            if matched_score >= 0.8:
                matched_files_dict[i] = j
            else:
                non_matched_files_dict[i] = "No parsed output available"

    for i in matched_files_dict:
        if i in non_matched_files_dict:
            del non_matched_files_dict[i]

    print("matched_files_dict =", matched_files_dict)
    print("non_matched_files_dict =", non_matched_files_dict)

    return matched_files_dict, non_matched_files_dict


def documentai_json_proto_downloader(
    bucket_name: str, blob_name_with_prefix_path: str
) -> documentai.Document:
    """
    Downloads a file from a specified Google Cloud Storage bucket
    and converts it into a DocumentAI Document proto.

    Args:
        bucket_name (str): The name of the GCS bucket from which to download the file.
        blob_name_with_prefix_path (str): The full path (prefix) to the JSON blob in the bucket.

    Returns:
        documentai.Document: A DocumentAI Document proto representation of the downloaded JSON.
    """

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name_with_prefix_path)

    doc = documentai.Document.from_json(blob.download_as_bytes())

    return doc


def copy_blob(
    bucket_name: str,
    blob_name: str,
    destination_bucket_name: str,
    destination_blob_name: str,
) -> None:
    """
    Copies a blob (file/object) from one GCP storage bucket to another.

    Args:
        bucket_name (str): Name of the source bucket.
        blob_name (str): Name of the blob (file/object) in the source bucket to be copied.
        destination_bucket_name (str): Name of the destination bucket.
        destination_blob_name (str): Desired name for the blob in the destination bucket.

    Output:
        None. The blob is copied to the destination bucket with the specified name.
    """
    storage_client = storage.Client()
    source_bucket = storage_client.bucket(bucket_name)
    source_blob = source_bucket.blob(blob_name)
    destination_bucket = storage_client.bucket(destination_bucket_name)
    source_bucket.copy_blob(source_blob, destination_bucket, destination_blob_name)


def get_entity_metadata(
    df: pd.DataFrame, entity: documentai.Document.Entity
) -> pd.DataFrame:
    """
    Parse the entity to extract bounding boxes,
    entity type, text and page number.

    Args:
        entity: Document AI entity object

    Returns:
        pandas.DataFrame: A DataFrame representation of the JSON with columns
                          ['type_', 'mention_text', 'bbox', 'page'].
                          'type_' column indicates the type of entity.
                          'mention_text' column contains the text of the entity or its property.
                          'bbox' column contains bounding box coordinates.
                          'page' column indicates the page number where the entity is found.
    """

    bbox = []
    bound_poly = entity.page_anchor.page_refs
    coordinates_xy = bound_poly[0].bounding_poly.normalized_vertices
    x1 = [xy.x for xy in coordinates_xy]
    y1 = [xy.y for xy in coordinates_xy]

    try:
        page = entity.page_anchor.page_refs[0].page
    except IndexError:
        page = 0
    bbox = [
        round(min(x1), 8),
        round(min(y1), 8),
        round(max(x1), 8),
        round(max(y1), 8),
    ]
    df.loc[len(df.index)] = [
        entity.type_,
        entity.mention_text,
        bbox,
        page,
    ]
    return df


def json_to_dataframe(data: documentai.Document) -> pd.DataFrame:
    """
    Converts a loaded DocumentAI proto JSON into a pandas DataFrame.

    Args:
        data (json object): A loaded DocumentAI Document proto JSON.

    Returns:
        pandas.DataFrame: A DataFrame representation of the JSON with columns
                          ['type_', 'mention_text', 'bbox', 'page'].
                          'type_' column indicates the type of entity.
                          'mention_text' column contains the text of the entity or its property.
                          'bbox' column contains bounding box coordinates.
                          'page' column indicates the page number where the entity is found.
    """

    df = pd.DataFrame(columns=["type_", "mention_text", "bbox", "page"])

    try:
        for entity in data.entities:
            # First, we'll assume it doesn't have properties
            has_properties = False

            # Check for subentities (properties)
            try:
                for subentity in entity.properties:
                    has_properties = True  # Mark that we found properties
                    try:
                        df = get_entity_metadata(df, subentity)
                    except (AttributeError, Exception) as e:
                        print(e)
                        continue

            except (AttributeError, Exception) as e:
                print(f"Exception encountered: {e}")
                continue

            # If no properties were found for the entity, add it to the dataframe
            if not has_properties:
                try:
                    df = get_entity_metadata(df, entity)
                except (AttributeError, Exception) as e:
                    print(f"Exception encountered: {e}")
                    continue

        return df
    except (AttributeError, Exception) as e:
        print(f"Exception encountered: {e}")
        return df


def blob_downloader(bucket_name: str, blob_name: str) -> Dict:
    """
    Downloads a JSON file from a specified Google Cloud Storage bucket
    and loads it as a Python dictionary.

    Args:
        bucket_name (str): The name of the GCS bucket from which to download the file.
        blob_name (str): The name or full path to the JSON blob in the bucket.

    Returns:
        dict: A dictionary representation of the downloaded JSON file.
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    contents = blob.download_as_string()
    return json.loads(contents.decode())


def bbox_maker(bounding_poly: List[Dict[str, float]]) -> List[float]:
    """
    Converts a bounding polygon (list of coordinates) into a bounding box represented by
    the minimum and maximum x and y values.

    Args:
        bounding_poly (list of dicts): A list of coordinates where each coordinate is a dictionary
                                      with "x" and "y" keys. Example: [{"x": 0.5, "y": 0.5}, ...]

    Returns:
        list: A list representing the bounding box in the format [min_x, min_y, max_x, max_y].
    """

    x_list = []
    y_list = []

    for i in bounding_poly:
        x_list.append(i["x"])
        y_list.append(i["y"])

    bbox = [min(x_list), min(y_list), max(x_list), max(y_list)]

    return bbox


def remove_row(df: pd.DataFrame, entity: Any) -> pd.DataFrame:
    """
    Removes rows from a DataFrame where the "type_" column matches the specified entity.

    Args:
        df (pandas.DataFrame): The input DataFrame from which rows need to be removed.
        entity (str): The entity value that should be used to identify rows to be removed.

    Returns:
        pandas.DataFrame: A DataFrame with rows removed where the "type_" column
        matches the specified entity.
    """

    return df[df["type_"] != entity]


def find_match(
    entity_file1: List[Union[str, List[float]]], df_file2: pd.DataFrame
) -> Optional[int]:
    """
    Identifies a matching entity from a DataFrame (`df_file2`)
    based on the Intersection Over Union (IOU)
    of bounding boxes with respect to a given entity (`entity_file1`).

    Args:
        entity_file1 (list): A list containing entity details from the first file.
                             It should have the format [type_, mention_text, bbox, ...].
        df_file2 (pandas.DataFrame): The input DataFrame containing entity details
        from the second file.

    Returns:
        int or None: The index of the matching entity from `df_file2` if found,
        otherwise None.

    Note:
        The function assumes the existence of a function `bb_intersection_over_union`
        that computes the IOU.
    """

    bbox_file1 = entity_file1[2]

    # Entity not present in json file
    if not bbox_file1:
        return None

    # Filtering entities with the same name
    df_file2 = df_file2[df_file2["type_"] == entity_file1[0]]

    # Calculating IOU values for the entities
    index_iou_pairs = []
    for index, entity_file2 in df_file2.iterrows():
        if entity_file2["bbox"]:
            iou = bb_intersection_over_union(bbox_file1, entity_file2["bbox"])
            index_iou_pairs.append((index, iou))

    # Choose entity with highest IOU, IOU should be at least > 0.2
    matched_index = None
    for index_iou in sorted(index_iou_pairs, key=operator.itemgetter(1), reverse=True):
        if index_iou[1] > 0.2:  # Threshold
            matched_index = index_iou[0]
            break

    return matched_index


def bb_intersection_over_union(box1: Any, box2: List[float]) -> float:
    """
    Calculates the Intersection Over Union (IOU) between two bounding boxes.

    The bounding boxes are represented as a list of coordinates: [x_min, y_min, x_max, y_max].

    Args:
        box1 (list[float]): Coordinates of the first bounding box.
        box2 (list[float]): Coordinates of the second bounding box.

    Returns:
        float: The IOU between the two bounding boxes.
        A value between 0 (no overlap) to 1 (complete overlap).

    Example:
        box1 = [0.1, 0.1, 0.6, 0.6]
        box2 = [0.5, 0.5, 1.0, 1.0]
        iou = bb_intersection_over_union(box1, box2)
    """

    # Determine the coordinates of the intersection rectangle
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    # Calculate the area of the intersection rectangle
    inter_area = max(0, x2 - x1) * max(0, y2 - y1)

    # If there's no intersection, IOU is 0
    if inter_area == 0:
        return 0

    # Calculate the area of each bounding box
    box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])

    # Calculate the IOU
    iou = inter_area / float(box1_area + box2_area - inter_area)

    return iou


def get_match_ratio(values: List[str]) -> float:
    """
    Calculates the similarity ratio between two strings using SequenceMatcher.

    Args:
        values (list[str]): A list containing four elements.
                            The second(index 1) and fourth(index 3) are the strings to be compared.

    Returns:
        float: A ratio representing the similarity between the two strings.
              A value between 0 (no similarity) and 1 (identical strings).

    Example:
        values = ["Name1", "apple", "Name2", "apples"]
        ratio = get_match_ratio(values)
    """
    file1_value = values[1]
    file2_value = values[2]

    if file1_value == "Entity not found." or file2_value == "Entity not found.":
        return 0
    return difflib.SequenceMatcher(a=file1_value, b=file2_value).ratio()


def compare_pre_hitl_and_post_hitl_output(
    file1: Any, file2: Any
) -> Tuple[DataFrame, float]:
    """
    Compares the entities between two files and returns the results in a DataFrame.

    Args:
        file1 (Any): DocumentAI Object of Json from the first file.
        file2 (Any): DocumentAI Object of Json from the second file.

    Returns:
        Tuple[DataFrame, float]: A tuple where the first element is a DataFrame based on the
                                comparison,and the second element is a float representing
                                the score.
    """
    df_file1 = json_to_dataframe(file1)
    df_file2 = json_to_dataframe(file2)
    file1_entities = [entity[0] for entity in df_file1.values]
    file2_entities = [entity[0] for entity in df_file2.values]

    # find entities which are present only once in both files
    # these entities will be matched directly
    common_entities = set(file1_entities).intersection(set(file2_entities))
    exclude_entities = []
    for entity in common_entities:
        if file1_entities.count(entity) > 1 or file2_entities.count(entity) > 1:
            exclude_entities.append(entity)
    for entity in exclude_entities:
        common_entities.remove(entity)
    df_compare = pd.DataFrame(
        columns=[
            "Entity Type",
            "Pre_HITL_Output",
            "Post_HITL_Output",
            "pre_bbox",
            "post_bbox",
            "page1",
            "page2",
        ]
    )
    for entity in common_entities:
        value1 = df_file1[df_file1["type_"] == entity].iloc[0]["mention_text"]
        value2 = df_file2[df_file2["type_"] == entity].iloc[0]["mention_text"]
        pre_bbox = df_file1[df_file1["type_"] == entity].iloc[0]["bbox"]
        post_bbox = df_file2[df_file2["type_"] == entity].iloc[0]["bbox"]
        page1 = df_file1[df_file1["type_"] == entity].iloc[0]["page"]
        page2 = df_file2[df_file2["type_"] == entity].iloc[0]["page"]
        df_compare.loc[len(df_compare.index)] = [
            entity,
            value1,
            value2,
            pre_bbox,
            post_bbox,
            page1,
            page2,
        ]
        # common entities are removed from df_file1 and df_file2
        df_file1 = remove_row(df_file1, entity)
        df_file2 = remove_row(df_file2, entity)

    # remaining entities are matched comparing the area of IOU across them
    mention_text2 = pd.Series(dtype=str)
    bbox2 = pd.Series(dtype=object)
    bbox1 = pd.Series(dtype=object)
    page_1 = pd.Series(dtype=object)
    page_2 = pd.Series(dtype=object)

    for index, row in enumerate(df_file1.values):
        matched_index = find_match(row, df_file2)
        if matched_index is not None:
            mention_text2.loc[index] = df_file2.loc[matched_index][1]
            bbox2.loc[index] = df_file2.loc[matched_index][2]
            bbox1.loc[index] = row[2]
            page_2.loc[index] = df_file2.loc[matched_index][3]
            page_1.loc[index] = row[3]
            df_file2 = df_file2.drop(matched_index)
        else:
            mention_text2.loc[index] = "Entity not found."
            bbox2.loc[index] = "Entity not found."
            bbox1.loc[index] = row[2]
            page_1.loc[index] = row[3]
            page_2.loc[index] = "no"

    df_file1["mention_text2"] = mention_text2.values
    df_file1["bbox2"] = bbox2.values
    df_file1["bbox1"] = bbox1.values
    df_file1["page_1"] = page_1.values
    df_file1["page_2"] = page_2.values

    df_file1 = df_file1.drop(["bbox"], axis=1)
    df_file1 = df_file1.drop(["page"], axis=1)
    df_file1.rename(
        columns={
            "type_": "Entity Type",
            "mention_text": "Pre_HITL_Output",
            "mention_text2": "Post_HITL_Output",
            "bbox1": "pre_bbox",
            "bbox2": "post_bbox",
            "page_1": "page1",
            "page_2": "page2",
        },
        inplace=True,
    )
    df_compare = df_compare.append(df_file1, ignore_index=True)
    # adding entities which are present in file2 but not in file1
    for row in df_file2.values:
        df_compare.loc[len(df_compare.index)] = [
            row[0],
            "Entity not found.",
            row[1],
            "[]",
            row[2],
            "[]",
            row[3],
        ]

    # df_compare['Match'] = df_compare['Ground Truth Text'] == df_compare['Output Text']
    match_array = []
    for i in range(0, len(df_compare)):
        match_string = ""
        not_found_string = "Entity not found."
        pre_output = df_compare.iloc[i]["Pre_HITL_Output"]
        post_output = df_compare.iloc[i]["Post_HITL_Output"]

        if pre_output == not_found_string and post_output == not_found_string:
            match_string = "TN"
        elif pre_output != not_found_string and post_output == not_found_string:
            match_string = "FN"
        elif pre_output == not_found_string and post_output != not_found_string:
            match_string = "FP"
        elif pre_output != not_found_string and post_output != not_found_string:
            match_string = "TP" if pre_output == post_output else "FP"
        else:
            match_string = "Something went Wrong."

        match_array.append(match_string)

    df_compare["Match"] = match_array

    df_compare["Fuzzy Ratio"] = df_compare.apply(get_match_ratio, axis=1)
    if list(df_compare.index):
        score = df_compare["Fuzzy Ratio"].sum() / len(df_compare.index)
    else:
        score = 0

    # display(df_compare)
    return df_compare, score


def get_document_schema(
    location: str, project_number: str, processor_id: str, processor_version_id: str
) -> Any:
    """
    Fetches the document schema of a specific processor version from Google Cloud DocumentAI.

    Args:
        location (str): The location of the DocumentAI service ("eu" or other values).
        project_number (str): The number representing the Google Cloud project.
        processor_id (str): The ID of the DocumentAI processor.
        processor_version_id (str): The ID of the processor version.

    Returns:
        documentai.types.Document.Schema: The document schema for the specified processor version.

    Example:
        schema = get_document_schema("eu", "123456", "processor123", "version123")
    """
    # Choose the endpoint based on the provided location.
    # You must set the `api_endpoint` if you use a location other than "us".
    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")

    # Initialize the DocumentAI client.
    client = documentai.DocumentProcessorServiceClient(client_options=opts)

    # The full resource name of the processor version
    # e.g.: projects/project_num/locations/location/processors/
    # processor_id/processorVersions/processor_version_id
    name = client.processor_version_path(
        project_number, location, processor_id, processor_version_id
    )
    # Fetch the processor version details.
    response = client.get_processor_version(name=name)

    # Extract and return the document schema.
    return response.document_schema


def create_pdf_bytes_from_json(gt_json: dict) -> Tuple[bytes, List[Any]]:
    """
    Create PDF bytes from the image content of the ground truth JSON,
    which will be used for the processing of files.

    Args:
        gt_json (dict): The input JSON data containing image content.

    Returns:
        bytes: The output PDF in byte format.
    """

    def decode_image(image_bytes: bytes) -> Image.Image:
        with io.BytesIO(image_bytes) as image_file:
            image = Image.open(image_file)
            image.load()
        return image

    def create_pdf_from_images(
        images: Sequence[Image.Image],
    ) -> bytes:
        """Creates a PDF from a sequence of images.

        The PDF will contain 1 page per image, in the same order.

        Args:
          images: A sequence of images.

        Returns:
          The PDF bytes.
        """
        if not images:
            raise ValueError("At least one image is required to create a PDF")

        # PIL PDF saver does not support RGBA images
        images = [
            image.convert("RGB") if image.mode == "RGBA" else image for image in images
        ]

        with io.BytesIO() as pdf_file:
            images[0].save(
                pdf_file, save_all=True, append_images=images[1:], format="PDF"
            )
            return pdf_file.getvalue()

    document = documentai.Document.from_json(json.dumps(gt_json))
    synthesized_images = [decode_image(page.image.content) for page in document.pages]
    pdf_bytes = create_pdf_from_images(synthesized_images)

    return pdf_bytes, synthesized_images


def process_document_sample(
    project_id: str,
    location: str,
    processor_id: str,
    pdf_bytes: bytes,
    processor_version: str,
):
    """This function is used to process the files using pdf bytes and provides the processed file"""
    # You must set the `api_endpoint` if you use a location other than "us".
    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    client = documentai.DocumentProcessorServiceClient(client_options=opts)

    name = client.processor_version_path(
        project_id, location, processor_id, processor_version
    )

    raw_document = documentai.RawDocument(
        content=pdf_bytes, mime_type="application/pdf"
    )

    # Configure the process request
    request = documentai.ProcessRequest(
        name=name, raw_document=raw_document, skip_human_review=False
    )

    # Recognizes text entities in the PDF document
    result = client.process_document(request=request)

    return result


def store_document_as_json(document, bucket_name: str, file_name: str):
    """
    Store Document json in cloud storage.
    """

    storage_client = storage.Client()
    process_result_bucket = storage_client.get_bucket(bucket_name)
    document_blob = storage.Blob(
        name=str(Path(file_name)), bucket=process_result_bucket
    )
    document_blob.upload_from_string(document, content_type="application/json")


def convert_and_upload_tiff_to_jpeg(
    project_id, bucket_name, input_tiff_path, output_jpeg_path
):
    """
    Convert a TIFF file from Google Cloud Storage to a JPEG file and upload it back.
    Args:
        project_id (str): The Google Cloud project ID.
        bucket_name (str): The name of the Google Cloud Storage bucket.
        input_tiff_path (str): The path of the TIFF file in the bucket to be converted.
        output_jpeg_path (str): The path where the converted JPEG file will be stored in the bucket.
    """
    from io import BytesIO

    try:
        # Initialize Google Cloud Storage client
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.get_bucket(bucket_name)

        # Download TIFF file from GCS
        blob = bucket.blob(input_tiff_path)
        tiff_file = BytesIO()
        blob.download_to_file(tiff_file)
        tiff_file.seek(0)

        # Convert to JPEG
        with Image.open(tiff_file) as im:
            rgb_im = im.convert("RGB")
            jpeg_file = BytesIO()
            rgb_im.save(jpeg_file, "JPEG")
            jpeg_file.seek(0)

        # Upload JPEG file to GCS
        blob = bucket.blob(output_jpeg_path)
        blob.upload_from_file(jpeg_file, content_type="image/jpeg")

    except storage.exceptions.GoogleCloudError as gce:
        print("Google Cloud Storage error: ", gce)
        return False
    except OSError as ose:
        print("File operation error: ", ose)
        return False
    except Exception as e:
        print("An unexpected error occurred: ", e)
        return False

    return True


def batch_process_documents_sample(
    project_id: str,
    location: str,
    processor_id: str,
    gcs_input_uri: str,
    gcs_output_uri: str,
    processor_version_id: Optional[str] = None,
    timeout: int = 500,
) -> Any:
    """It will perform Batch Process on raw input documents

    Args:
        project_id (str): GCP project ID
        location (str): Processor location us or eu
        processor_id (str): GCP DocumentAI ProcessorID
        gcs_input_uri (str): GCS path which contains all input files
        gcs_output_uri (str): GCS path to store processed JSON results
        processor_version_id (str, optional): VersionID of GCP DocumentAI Processor. Defaults to None.
        timeout (int, optional): Maximum waiting time for operation to complete. Defaults to 500.

    Returns:
        operation.Operation: LRO operation ID for current batch-job
    """

    opts = {"api_endpoint": f"{location}-documentai.googleapis.com"}
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    input_config = documentai.BatchDocumentsInputConfig(
        gcs_prefix=documentai.GcsPrefix(gcs_uri_prefix=gcs_input_uri)
    )
    output_config = documentai.DocumentOutputConfig(
        gcs_output_config={"gcs_uri": gcs_output_uri}
    )
    print("Documents are processing(batch-documents)...")
    name = (
        client.processor_version_path(
            project_id, location, processor_id, processor_version_id
        )
        if processor_version_id
        else client.processor_path(project_id, location, processor_id)
    )
    request = documentai.types.document_processor_service.BatchProcessRequest(
        name=name,
        input_documents=input_config,
        document_output_config=output_config,
    )
    operation = client.batch_process_documents(request)
    print("Waiting for operation to complete...")
    operation.result(timeout=timeout)
    return operation
