# pylint: disable=C0301
# pylint: disable=R0914
# pylint: disable=R1702
# pylint: disable=R0912
# pylint: disable=E1133
# pylint: disable=E1101
"""This file will compare two JSONS and uploads the xlsx file to GCS Bucket."""
from collections import Counter
from typing import Any, Dict, List

from google.cloud import documentai_v1beta3 as documentai
from google.cloud import storage
import pandas as pd


def upload_xlsx_to_gcs(
    bucket_name: str, source_file_path: str, destination_blob_name: str
) -> None:
    """
    Uploads an XLSX file to a Google Cloud Storage bucket.

    Args:
        bucket_name (str): The name of the GCS bucket.
        source_file_path (str): The local file path of the XLSX file to upload.
        destination_blob_name (str): The destination path (including filename) in GCS.

    Returns:
        None
    """

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_path)

    print(
        f"File {source_file_path} uploaded to gs://{bucket_name}/{destination_blob_name}"
    )


def calculate_bbox_overlap(box1: List[float], box2: List[float]) -> float:
    """
    Calculates the Intersection Over Union (IOU) percentage between two bounding boxes.

    Bounding boxes are represented as a list of coordinates: [x_min, y_min, x_max, y_max].

    Args:
        box1 (List[float]): Coordinates of the first bounding box.
        box2 (List[float]): Coordinates of the second bounding box.

    Returns:
        float: The IOU percentage between the two bounding boxes.
        A value between 0 (no overlap) and 100 (complete overlap).

    Example:
        box1 = [0.1, 0.1, 0.6, 0.6]
        box2 = [0.5, 0.5, 1.0, 1.0]
        iou = calculate_bbox_overlap(box1, box2)  # Returns IOU as a percentage
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

    return iou * 100


def read_json_files_from_gcs(
    bucket_name: str, folder_prefixes: List[str]
) -> List[Dict[str, Any]]:
    """
    Reads JSON files from a Google Cloud Storage (GCS) bucket, parses the data using Google Document AI,
    and extracts entity information including bounding box coordinates.

    Args:
        bucket_name (str): The name of the GCS bucket.
        folder_prefixes (List[str]): List of folder prefixes to search for JSON files.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing extracted entity data.

    Extracted data includes:
        - folder_index: Index of the folder in `folder_prefixes`.
        - filename: The name of the JSON file.
        - Entity_name: Name of the detected entity.
        - Text: Extracted text for the entity.
        - Page_Number: Page number where the entity is located.
        - Bounding_Box: Normalized bounding box coordinates [x_min, y_min, x_max, y_max].

    Example Usage:
        data = read_json_files_from_gcs("my-bucket", ["folder1/", "folder2/"])
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    data = []

    for folder_index, folder_prefix in enumerate(folder_prefixes, start=1):
        blobs = bucket.list_blobs(prefix=folder_prefix)

        for blob in blobs:
            if blob.name.endswith(".json"):
                # json_data = json.loads(blob.download_as_text())
                json_data = documentai.Document.from_json(blob.download_as_bytes())
                # json_data=documentai.Document.to_dict(doc)
                # if hasattr(json_data, "entities") and isinstance(json_data.entities, list):
                for entity in json_data.entities:
                    if entity.properties == []:
                        # print(entity.keys())
                        entity_name = entity.type_
                        mention_text = entity.mention_text
                        if entity.page_anchor.page_refs:
                            page_number = entity.page_anchor.page_refs[0].page
                        else:
                            page_number = 0
                        # print(page_number)
                        if (
                            entity.page_anchor.page_refs
                            and "bounding_poly" in entity.page_anchor.page_refs[0]
                        ):
                            bounding_poly = entity.page_anchor.page_refs[
                                0
                            ].bounding_poly.normalized_vertices
                        else:
                            bounding_poly = [0, 0, 0, 0]

                        x_cordinates = []
                        y_cordinates = []

                        if bounding_poly != [0, 0, 0, 0]:
                            for xy in bounding_poly:
                                x_cordinates.append(xy.x)
                                y_cordinates.append(xy.y)

                            bounding_box = (
                                [
                                    min(x_cordinates),
                                    min(y_cordinates),
                                    max(x_cordinates),
                                    max(y_cordinates),
                                ]
                                if len(bounding_poly) >= 4
                                else [0, 0, 0, 0]
                            )
                        # print(blob.name.split('/')[-1])

                        data.append(
                            {
                                "folder_index": folder_index,
                                "filename": blob.name.split("/")[-1],
                                "Entity_name": entity_name,
                                "Text": mention_text,
                                "Page_Number": page_number,
                                "Bounding_Box": bounding_box,
                            }
                        )
                    else:
                        for child in entity.properties:
                            entity_name = entity.type_ + "/" + child.type_
                            mention_text = child.mention_text
                            page_number = child.page_anchor.page_refs[0].page
                            bounding_poly = child.page_anchor.page_refs[
                                0
                            ].bounding_poly.normalized_vertices

                            x_cordinates = []
                            y_cordinates = []

                            for xy in bounding_poly:
                                x_cordinates.append(xy.x)
                                y_cordinates.append(xy.y)

                            bounding_box = (
                                [
                                    min(x_cordinates),
                                    min(y_cordinates),
                                    max(x_cordinates),
                                    max(y_cordinates),
                                ]
                                if len(bounding_poly) >= 4
                                else [0, 0, 0, 0]
                            )
                            # print(blob.name.split('/')[-1])

                            data.append(
                                {
                                    "folder_index": folder_index,
                                    "filename": blob.name.split("/")[-1],
                                    "Entity_name": entity_name,
                                    "Text": mention_text,
                                    "Page_Number": page_number,
                                    "Bounding_Box": bounding_box,
                                }
                            )

    # df = pd.DataFrame(data)
    # df.to_csv("data.csv", index=False)
    return data


def calculate_consistency(
    data: List[Dict[str, Any]], num_folders: int
) -> List[Dict[str, Any]]:
    """
    Calculates the consistency percentage of extracted entities based on mention text,
    page number, and bounding box overlap across multiple folders.

    Args:
        data (List[Dict[str, Any]]): List of entity data extracted from multiple folders.
            Each entity should have:
                - 'Entity_name': Name of the detected entity.
                - 'Text': Extracted mention text.
                - 'Page_Number': Page number where the entity appears.
                - 'Bounding_Box': Normalized bounding box coordinates [x_min, y_min, x_max, y_max].
                - 'filename': Name of the file.
                - 'folder_index': Index of the folder in which the entity was found.
        num_folders (int): Total number of folders being compared.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing:
            - FileName: Name of the JSON file.
            - Entity_name: Name of the detected entity.
            - Page_Number: Page number of the entity.
            - Majority_Text: The most common mention text across folders.
            - Consistency_Percentage: Percentage consistency of the entity across folders.
            - Folder_N_Text, Folder_N_Bounding_Box, Folder_N_page_number:
            Mention text, bounding box, and page number for each folder.

    Example:
        results = calculate_consistency(extracted_data, num_folders=3)
    """
    grouped_data = {}

    for entity in data:
        # print(entity)
        grouped = False
        for key, dic_value in grouped_data.items():
            # print(entity['Entity_name'],key[0],entity['Page_Number'],key[1],entity['filename'],key[2])
            if (
                entity["Entity_name"] == key[0]
                and int(entity["Page_Number"]) == int(key[1])
                and entity["filename"] == key[2]
            ):
                # print(grouped_data[key])
                for compare_entity in dic_value:
                    overlap = calculate_bbox_overlap(
                        entity["Bounding_Box"], compare_entity["Bounding_Box"]
                    )
                    # print(overlap)
                    # print(entity['Bounding_Box'], compare_entity['Bounding_Box'],compare_entity["Text"],entity["Text"])
                    if overlap >= 40:
                        dic_value.append(entity)
                        grouped = True
                        break
                if grouped:
                    break
        if not grouped:
            # print(entity['Page_Number'])
            key = (
                entity["Entity_name"],
                str(entity["Page_Number"]),
                entity["filename"],
                tuple(entity["Bounding_Box"]),
            )
            if key not in grouped_data:
                grouped_data[key] = []
            grouped_data[key].append(entity)
    # print(grouped_data)
    results = []

    for key, entities in grouped_data.items():
        mention_texts = [entity["Text"] for entity in entities]
        # folder_indices = [entity['folder_index'] for entity in entities]

        mention_text_counter = Counter(mention_texts)
        majority_text, majority_count = mention_text_counter.most_common(1)[0]
        # print( key[0],majority_count,num_folders)

        consistency_percentage = (majority_count / num_folders) * 100
        # print(key[0],key[1],key[2])
        result = {
            "FileName": key[2],
            "Entity_name": key[0],
            "Page_Number": key[1],
            "Majority_Text": majority_text,
            "Consistency_Percentage": consistency_percentage,
        }

        for i in range(1, num_folders + 1):
            result[f"Folder_{i}_Text"] = None
            result[f"Folder_{i}_Bounding_Box"] = None
            result[f"Folder_{i}_page_number"] = None

        # print(entities)
        for entity in entities:
            # print(entity)
            result[f'Folder_{entity["folder_index"]}_Text'] = entity["Text"]
            result[f'Folder_{entity["folder_index"]}_Bounding_Box'] = entity[
                "Bounding_Box"
            ]
            result[f'Folder_{entity["folder_index"]}_page_number'] = entity[
                "Page_Number"
            ]
            # print(entity['Page_Number'])

        results.append(result)

    return results


def calculate_document_level_consistency(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate document-level consistency.

    Args:
        df (pd.DataFrame): DataFrame containing the consistency data with a column 'FileName'
                            for file names and 'Consistency_Percentage' for consistency values.

    Returns:
        pd.DataFrame: A DataFrame with the average consistency percentage for each document,
                      with columns 'FileName' and 'Average_Document_Consistency'.
    """
    doc_consistency = df.groupby("FileName").Consistency_Percentage.mean().reset_index()
    doc_consistency.rename(
        columns={"Consistency_Percentage": "Average_Document_Consistency"}, inplace=True
    )
    return doc_consistency


def calculate_entity_level_consistency(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate entity-level consistency.

    Args:
        df (pd.DataFrame): DataFrame containing the consistency data with a column 'Entity_name'
                            for entity names and 'Consistency_Percentage' for consistency values.

    Returns:
        pd.DataFrame: A DataFrame with the average, minimum, and maximum consistency percentage
                      for each entity, with columns 'Entity_name', 'Average_Entity_Consistency',
                      'Min_Entity_Consistency', and 'Max_Entity_Consistency'.
    """
    entity_consistency = (
        df.groupby("Entity_name")
        .Consistency_Percentage.agg(["mean", "min", "max"])
        .reset_index()
    )
    entity_consistency.rename(
        columns={
            "mean": "Average_Entity_Consistency",
            "min": "Min_Entity_Consistency",
            "max": "Max_Entity_Consistency",
        },
        inplace=True,
    )
    return entity_consistency


def save_to_xlsx(
    df: pd.DataFrame,
    doc_consistency: pd.DataFrame,
    entity_consistency: pd.DataFrame,
    output_path: str,
) -> None:
    """
    Save the dataframes to an XLSX file with multiple sheets.

    Args:
        df (pd.DataFrame): The main dataframe to be saved, typically containing entity-level comparisons.
        doc_consistency (pd.DataFrame): DataFrame with document-level consistency data.
        entity_consistency (pd.DataFrame): DataFrame with entity-level consistency data.
        output_path (str): The file path where the XLSX file will be saved.

    Returns:
        None
    """
    with pd.ExcelWriter(output_path) as writer:
        df.to_excel(writer, sheet_name="Entity Comparisons", index=False)
        doc_consistency.to_excel(
            writer, sheet_name="Document Level Consistency", index=False
        )
        entity_consistency.to_excel(
            writer, sheet_name="Entity Level Consistency", index=False
        )


def main(
    path: str, iteration: int, output_file_name: str, gcs_result_path: str, date: str
) -> None:
    """
    Main function to process consistency data from Google Cloud Storage (GCS), calculate metrics, and save results.

    Args:
        path (str): The GCS path where the input data is located.
        iteration (int): The number of iterations to process.
        output_file_name (str): The base name for the output file.
        gcs_result_path (str): The GCS path where the result file will be uploaded.
        date (str): The date to be appended to the output file name.

    Returns:
        None
    """
    gcs_input_path = path
    bucket_name = gcs_input_path.split("/")[2]
    folder_prefixes = [
        "/".join(gcs_input_path.split("/")[3:]) + "iteration_" + str(i) + "/"
        for i in range(1, int(iteration) + 1)
    ]

    # Read JSON files directly from GCS
    data = read_json_files_from_gcs(bucket_name, folder_prefixes)

    # Calculate consistency metrics
    results = calculate_consistency(data, len(folder_prefixes))

    # Sort the result list by 'FileName'
    sorted_result = sorted(results, key=lambda x: x["FileName"])
    # Convert to DataFrame and save to CSV
    df = pd.DataFrame(sorted_result)

    doc_consistency = calculate_document_level_consistency(df)
    entity_consistency = calculate_entity_level_consistency(df)
    file_name = output_file_name + "_output.xlsx"
    save_to_xlsx(df, doc_consistency, entity_consistency, file_name)
    upload_xlsx_to_gcs(
        gcs_result_path.split("/")[2],
        file_name,
        "/".join(gcs_result_path.split("/")[3:])
        + f"consistency/{file_name.split('.')[0]}_{date}.xlsx",
    )

    # df.to_csv(file_name, index=False)
    print(output_file_name + " dataframe_created")
