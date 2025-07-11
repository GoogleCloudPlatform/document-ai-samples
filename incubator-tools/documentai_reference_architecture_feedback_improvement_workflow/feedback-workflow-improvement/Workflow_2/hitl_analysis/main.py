"""
HITL Analysis
"""

# pylint: disable=E0401
# pylint: disable=W0613
# pylint: disable=R0914
# pylint: disable=R0912
# pylint: disable=R0915
# pylint: disable=W0718
# pylint: disable=W0702
# pylint: disable=C0206
# pylint: disable=R0801

import datetime
import difflib
import json
import operator
import re
import traceback
from typing import List, Tuple
import warnings

import functions_framework
from google.cloud import bigquery
from google.cloud import storage
import pandas as pd

warnings.simplefilter(action="ignore", category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'


#  Start generating analysis report b/w pre&post hitl data
# checking whether bucket exists else create temperary bucket
def check_create_bucket(bucket_name: str) -> object:
    """This Function is to create a temperary bucket
    for storing the processed files
    args: name of bucket"""

    storage_client = storage.Client()
    try:
        bucket = storage_client.get_bucket(bucket_name)
        print(f"Bucket {bucket_name} already exists.")
    except Exception as e:
        bucket = storage_client.create_bucket(bucket_name)
        print(f"Bucket {bucket_name} created.")
        print(e)
    return bucket


def bucket_delete(bucket_name: str) -> None:
    """This function deltes the bucket and used for deleting the temporary
    bucket
    args: bucket name"""
    storage_client = storage.Client()
    try:
        bucket = storage_client.get_bucket(bucket_name)
        bucket.delete(force=True)
    except Exception as e:
        print(e)


def file_names(file_path: str) -> Tuple[list[str], dict[str, str]]:
    """
    Loads the GCS bucket and returns:
    - list of file names
    - dictionary mapping file name to full path

    Args:
        file_path (str): GCS path (e.g., gs://bucket/path/to/folder)

    Returns:
        Tuple[list[str], dict[str, str]]
    """
    bucket = file_path.split("/")[2]
    file_names_list = []
    file_dict = {}
    storage_client = storage.Client()
    source_bucket = storage_client.get_bucket(bucket)
    filenames = [
        blob.name
        for blob in source_bucket.list_blobs(prefix="/".join(file_path.split("/")[3:]))
    ]
    for filename in filenames:
        x = filename.split("/")[-1]
        if x != "":
            file_names_list.append(x)
            file_dict[x] = filename
    return file_names_list, file_dict


def list_blobs(bucket_name: str) -> List:
    """This function will give the list of files in a bucket
    args: gcs bucket name
    output: list of files"""
    blob_list = []
    storage_client = storage.Client()
    blobs = storage_client.list_blobs(bucket_name)
    for blob in blobs:
        blob_list.append(blob.name)
    return blob_list


# Bucket operations
def relation_dict_generator(
    pre_hitl_output_bucket: str, post_hitl_output_bucket: str
) -> Tuple:
    """This Function will check the files from pre_hitl_output_bucket and post_hitl_output_bucket
    and finds the json with same names(relation)"""
    pre_hitl_bucket_blobs = list_blobs(pre_hitl_output_bucket)
    post_hitl_bucket_blobs = list_blobs(post_hitl_output_bucket)

    relation_dict = {}
    non_relation_dict = {}
    for i in pre_hitl_bucket_blobs:
        for j in post_hitl_bucket_blobs:
            matched_score = difflib.SequenceMatcher(None, i, j).ratio()
            if matched_score > 0.9:
                relation_dict[i] = j
            else:
                non_relation_dict[i] = "NO POST HITL OUTPUT AVAILABLE"
                # print(i)
    for i in relation_dict:
        if i in non_relation_dict:
            del non_relation_dict[i]

    return relation_dict, non_relation_dict


def blob_downloader(bucket_name: str, blob_name: str) -> dict:
    """This Function is used to download the files from gcs bucket"""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    contents = blob.download_as_string()
    return json.loads(contents.decode())


def copy_blob(
    bucket_name: str,
    blob_name: str,
    destination_bucket_name: str,
    destination_blob_name: str,
) -> None:
    """This Method will copy files from one bucket(or folder) to another"""
    storage_client = storage.Client()
    source_bucket = storage_client.bucket(bucket_name)
    source_blob = source_bucket.blob(blob_name)
    destination_bucket = storage_client.bucket(destination_bucket_name)
    source_bucket.copy_blob(source_blob, destination_bucket, destination_blob_name)


def bbox_maker(bounding_poly):
    """Gathers the Bounding Poly of x,y"""
    x_list = []
    y_list = []
    for i in bounding_poly:
        x_list.append(i["x"])
        y_list.append(i["y"])
    bbox = [min(x_list), min(y_list), max(x_list), max(y_list)]
    return bbox


def json_to_dataframe(data: dict) -> pd.DataFrame:
    """Returns entities in dataframe format"""
    df = pd.DataFrame(columns=["type", "mentionText", "bbox"])

    if "entities" not in data.keys():
        return df

    for entity in data["entities"]:
        if "properties" in entity and len(entity["properties"]) > 0:
            for sub_entity in entity["properties"]:
                if "type" in sub_entity:
                    try:
                        bounding_poly = sub_entity["pageAnchor"]["pageRefs"][0][
                            "boundingPoly"
                        ]["normalizedVertices"]
                        bbox = bbox_maker(bounding_poly)
                        df.loc[len(df.index)] = [
                            sub_entity["type"],
                            sub_entity["mentionText"],
                            bbox,
                        ]
                    except KeyError:
                        if "mentionText" in sub_entity:
                            df.loc[len(df.index)] = [
                                sub_entity["type"],
                                sub_entity["mentionText"],
                                [],
                            ]
                        else:
                            df.loc[len(df.index)] = [
                                sub_entity["type"],
                                "Entity not found.",
                                [],
                            ]
        elif "type" in entity:
            try:
                bounding_poly = entity["pageAnchor"]["pageRefs"][0]["boundingPoly"][
                    "normalizedVertices"
                ]
                bbox = bbox_maker(bounding_poly)
                df.loc[len(df.index)] = [entity["type"], entity["mentionText"], bbox]
            except KeyError:
                if "mentionText" in entity:
                    df.loc[len(df.index)] = [entity["type"], entity["mentionText"], []]
                else:
                    df.loc[len(df.index)] = [entity["type"], "Entity not found.", []]
    return df


def remove_row(df, entity):
    """Drops the entity passed from the dataframe"""
    return df[df["type"] != entity]


def find_match(entity_file1, df_file2):
    """Finds the matching entity from the dataframe using
    the area of IOU between bboxes reference
    """
    bbox_file1 = entity_file1[2]
    # Entity not present in json file
    if not bbox_file1:
        return None

    # filtering entities with the same name
    df_file2 = df_file2[df_file2["type"] == entity_file1[0]]

    # calculating IOU values for the entities
    index_iou_pairs = []
    for index, entity_file2 in enumerate(df_file2.values):
        if entity_file2[2]:
            iou = bbintersection_over_union(bbox_file1, entity_file2[2])
            index_iou_pairs.append((index, iou))

    # choose entity with highest IOU, IOU should be atleast > 0.5
    matched_index = None
    for index_iou in sorted(index_iou_pairs, key=operator.itemgetter(1), reverse=True):
        if index_iou[1] > 0.5:
            matched_index = df_file2.index[index_iou[0]]
            break
    return matched_index


def bbintersection_over_union(box1, box2):
    """Calculates the area of IOU between two bounding boxes"""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter_area = abs(max((x2 - x1, 0)) * max((y2 - y1), 0))
    if inter_area == 0:
        return 0
    box1_area = abs((box1[2] - box1[0]) * (box1[3] - box1[1]))
    box2_area = abs((box2[2] - box2[0]) * (box2[3] - box2[1]))
    iou = inter_area / float(box1_area + box2_area - inter_area)

    return iou


def getmatch_ratio(values):
    """Get Match Ratio of Two files"""
    file1_value = values[1]
    file2_value = values[2]
    if file1_value == "Entity not found." or file2_value == "Entity not found.":
        return 0

    return difflib.SequenceMatcher(a=file1_value, b=file2_value).ratio()


def compare_pre_hitl_and_post_hitl_output(file1, file2):
    """Compares the entities between two files and returns
    the results in a dataframe
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
        columns=["Entity Type", "Pre_HITL_Output", "Post_HITL_Output"]
    )
    for entity in common_entities:
        value1 = df_file1[df_file1["type"] == entity].iloc[0]["mentionText"]
        value2 = df_file2[df_file2["type"] == entity].iloc[0]["mentionText"]
        df_compare.loc[len(df_compare.index)] = [entity, value1, value2]

        # common entities are removed from df_file1 and df_file2
        df_file1 = remove_row(df_file1, entity)
        df_file2 = remove_row(df_file2, entity)

    # remaining entities are matched comparing the area of IOU across them
    mention_text2 = pd.Series(dtype=str)
    for index, row in enumerate(df_file1.values):
        matched_index = find_match(row, df_file2)
        if matched_index is not None:
            mention_text2.loc[index] = df_file2.loc[matched_index][1]
            df_file2 = df_file2.drop(matched_index)
        else:
            mention_text2.loc[index] = "Entity not found."

    df_file1["mentionText2"] = mention_text2.values
    df_file1 = df_file1.drop(["bbox"], axis=1)
    df_file1.rename(
        columns={
            "type": "Entity Type",
            "mentionText": "Pre_HITL_Output",
            "mentionText2": "Post_HITL_Output",
        },
        inplace=True,
    )
    # df_compare = df_compare.append(df_file1, ignore_index=True)
    df_compare = pd.concat([df_compare, df_file1], ignore_index=True)

    # adding entities which are present in file2 but not in file1
    for row in df_file2.values:
        df_compare.loc[len(df_compare.index)] = [row[0], "Entity not found.", row[1]]

    # df_compare['Match'] = df_compare['Ground Truth Text'] == df_compare['Output Text']
    match_array = []
    for i in range(0, len(df_compare)):
        match_string = ""
        if (
            df_compare.iloc[i]["Pre_HITL_Output"] == "Entity not found."
            and df_compare.iloc[i]["Post_HITL_Output"] == "Entity not found."
        ):
            match_string = "TN"
        elif (
            df_compare.iloc[i]["Pre_HITL_Output"] != "Entity not found."
            and df_compare.iloc[i]["Post_HITL_Output"] == "Entity not found."
        ):
            match_string = "FN"
        elif (
            df_compare.iloc[i]["Pre_HITL_Output"] == "Entity not found."
            and df_compare.iloc[i]["Post_HITL_Output"] != "Entity not found."
        ):
            match_string = "FP"
        elif (
            df_compare.iloc[i]["Pre_HITL_Output"] != "Entity not found."
            and df_compare.iloc[i]["Post_HITL_Output"] != "Entity not found."
        ):
            if (
                df_compare.iloc[i]["Pre_HITL_Output"]
                == df_compare.iloc[i]["Post_HITL_Output"]
            ):
                match_string = "TP"
            else:
                match_string = "FP"
        else:
            match_string = "Something went Wrong."

        match_array.append(match_string)

    df_compare["Match"] = match_array

    df_compare["Fuzzy Ratio"] = df_compare.apply(getmatch_ratio, axis=1)
    if list(df_compare.index):
        score = df_compare["Fuzzy Ratio"].sum() / len(df_compare.index)
    else:
        score = 0
    return df_compare, score


def generate_compare_analysis_report(
    project_id, pre_hitl_output_uri, post_hitl_output_uri
):
    """Compare two files and generate analysis report"""
    compare_merged = pd.DataFrame()
    try:
        # creating temperary buckets

        now = str(datetime.datetime.now())
        now = re.sub(r"\W+", "", now)

        print("Creating temporary buckets")
        pre_hitl_bucket_name_temp = "pre_hitl_output" + "_" + now
        post_hitl_bucket_name_temp = "post_hitl_output_temp" + "_" + now
        # bucket name and prefix
        pre_hitl_bucket = pre_hitl_output_uri.split("/")[2]
        post_hitl_bucket = post_hitl_output_uri.split("/")[2]
        # getting all files and copying to temporary folder

        try:
            check_create_bucket(pre_hitl_bucket_name_temp)
            check_create_bucket(post_hitl_bucket_name_temp)
        except Exception as e:
            print("unable to create bucket because of exception : ", e)

        try:
            pre_hitl_output_files, pre_hitl_output_dict = file_names(
                pre_hitl_output_uri
            )
            post_hitl_output_files, post_hitl_output_dict = file_names(
                post_hitl_output_uri
            )
            print("copying files to temporary bucket")
            for i in pre_hitl_output_files:
                copy_blob(
                    pre_hitl_bucket,
                    pre_hitl_output_dict[i],
                    pre_hitl_bucket_name_temp,
                    i,
                )
            for i in post_hitl_output_files:
                copy_blob(
                    post_hitl_bucket,
                    post_hitl_output_dict[i],
                    post_hitl_bucket_name_temp,
                    i,
                )
            # pre_HITL_files_list = list_blobs(pre_hitl_bucket_name_temp)
            # post_HITL_files_list = list_blobs(post_hitl_bucket_name_temp)
        except Exception as e:
            print("unable to get list of files in buckets because : ", e)
        # processing the files and saving the files in temporary gCP bucket

        relation_dict, non_relation_dict = relation_dict_generator(
            pre_hitl_bucket_name_temp, post_hitl_bucket_name_temp
        )
        compare_merged = pd.DataFrame()
        # accuracy_docs = []
        print("comparing the PRE-HITL Jsons and POST-HITL jsons ....Wait for Summary ")
        for i in relation_dict:
            pre_hitl_json = blob_downloader(pre_hitl_bucket_name_temp, i)
            post_hitl_json = blob_downloader(
                post_hitl_bucket_name_temp, relation_dict[i]
            )
            compare_output = compare_pre_hitl_and_post_hitl_output(
                pre_hitl_json, post_hitl_json
            )[0]
            column = [relation_dict[i]] * compare_output.shape[0]
            # print(column)
            compare_output.insert(loc=0, column="File Name", value=column)

            compare_output.insert(loc=5, column="hitl_update", value=" ")
            for j in range(len(compare_output)):
                if compare_output["Fuzzy Ratio"][j] != 1.0:
                    if (
                        compare_output["Pre_HITL_Output"][j] == "Entity not found."
                        and compare_output["Post_HITL_Output"][j] == "Entity not found."
                    ):
                        compare_output["hitl_update"][j] = "NO"
                    else:
                        compare_output["hitl_update"][j] = "YES"
                else:
                    compare_output["hitl_update"][j] = "NO"
            for k in range(len(compare_output)):
                if compare_output["Fuzzy Ratio"][k] != 1.0:
                    hitl_update = "HITL UPDATED"
                    print(hitl_update)
                    break
                compare_output["hitl_update"][k] = "NO"

            # new_row=pd.Series([i,"Entities","are updated","by HITL",":",np.nan,hitl_update],
            # index=compare_output.columns)
            # compare_output=compare_output.append(new_row,ignore_index= True)
            frames = [compare_merged, compare_output]
            compare_merged = pd.concat(frames)
        try:
            bucket_delete(pre_hitl_bucket_name_temp)
            print("Deleting temporary buckets created")
            bucket_delete(post_hitl_bucket_name_temp)
        except Exception as e:
            print(e)
        compare_merged.drop(["Match", "Fuzzy Ratio"], axis=1, inplace=True)

        for k in non_relation_dict:
            new_row = pd.Series(
                [k, "-", "-", "-", non_relation_dict[k]], index=compare_merged.columns
            )
            # compare_merged = compare_merged.append(new_row, ignore_index=True)
            compare_merged = pd.concat([compare_merged, new_row], ignore_index=True)
        compare_merged.to_csv("compare_analysis.csv")
        entity_change = compare_merged.loc[compare_merged["hitl_update"] == "YES"]
        print(entity_change)

        print("CSV file created")
        print("***********ENTITIES UPDATED IN HITL**********")
        print("\n")
        print("rows, cols ", len(compare_merged), len(compare_merged.columns))
        print("\n")
        print("For More details look into CSV created")
        print("\n")
    except Exception as e:
        try:
            bucket_delete(pre_hitl_bucket_name_temp)
            bucket_delete(post_hitl_bucket_name_temp)
            print("unable to process the file   : ", e)
        except Exception as e1:
            print("unable to process the file   : ", e1)
    return compare_merged


def create_bigquery_dataset(bq_client, project_id, dataset_id):
    """Create a Bigquery Dataset"""
    dataset_name = f"{project_id}.{dataset_id}"

    # Check if dataset already exists
    try:
        dataset = bq_client.get_dataset(dataset_name)  # API request
        print(f"Dataset already exists: {dataset_name}")
    except Exception as e:
        print(e)
        # Dataset does not exist, create it
        dataset = bigquery.Dataset(dataset_name)
        dataset = bq_client.create_dataset(dataset)  # API request
        print(f"Created BigQuery dataset: {dataset_name}")


def create_bigquery_table(bq_client, project_id, dataset_id, table_id):
    """Create a bigquery Table"""
    table_name = f"{project_id}.{dataset_id}.{table_id}"
    schema = [
        bigquery.SchemaField("document_path", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("batch_id", "STRING"),
        bigquery.SchemaField(
            "created_at",
            "TIMESTAMP",
            mode="REQUIRED",
            default_value_expression="CURRENT_TIMESTAMP",
        ),
    ]

    table = bigquery.Table(table_name, schema=schema)
    table = bq_client.create_table(table, exists_ok=True)
    print(f"Created BigQuery table: {table_name}")


def load_data_bigquery(project_id, dataset_id, table_id, df):
    """Loading Data to a Bigquery Table"""
    bc = bigquery.Client()
    # Creating bigquery dataset and table if doesn't exist
    create_bigquery_dataset(bc, project_id, dataset_id)
    create_bigquery_table(bc, project_id, dataset_id, table_id)

    table_uri = f"{project_id}.{dataset_id}.{table_id}"
    print(f"Loading data to Bigquery {table_uri}")

    # dataset_ref = bigquery.DatasetReference(project=project_id, dataset_id=dataset_id)
    # dataset = bigquery.Dataset(dataset_ref)
    # dataset = bc.create_dataset(dataset, exists_ok=True)
    cols = list(map(lambda x: x.replace(" ", "_").lower(), df.columns))
    df.columns = cols
    table = bigquery.Table(table_ref=table_uri)
    # table = bc.create_table(table, exists_ok=True)
    bc.delete_table(table)
    load_job = bc.load_table_from_dataframe(df, table)
    print("\tSuccessfully loaded data.", load_job)


@functions_framework.http
def hitl_analysis(request):
    """Cloud Function to update hitl analysis to Bigquery"""
    try:
        request_json = request.get_json(silent=True)
        if request_json:
            project_id = request_json.get("project_id")
            pre_hitl_output_uri = request_json.get("pre_HITL_output_URI")
            post_hitl_output_uri = request_json.get("post_HITL_output_URI")
            dataset_id = request_json.get("dataset_id")
            table_id = request_json.get("table_id")
        else:
            project_id = request.args.get("project_id")
            pre_hitl_output_uri = request.args.get("pre_HITL_output_URI")
            post_hitl_output_uri = request.args.get("post_HITL_output_URI")
            dataset_id = request_json.get("dataset_id")
            table_id = request_json.get("table_id")

        try:
            #  Generating Analysis report pre&post HITL
            df = generate_compare_analysis_report(
                project_id, pre_hitl_output_uri, post_hitl_output_uri
            )

            # Load analysis report to Bigquery
            load_data_bigquery(project_id, dataset_id, table_id, df)

            return (
                {
                    "state": "SUCCESS",
                    "message": f"""Analysis completed and status
            updated in BigQuery table {project_id}.{dataset_id}.{table_id}""",
                },
                200,
            )

        except Exception as e:
            print(e)
            return (
                {
                    "state": "FAILED",
                    "message": f"""UNABLE TO COMPLETE BECAUSE OF {e},
            {traceback.format_exc()}""",
                },
                500,
            )

    except Exception as e:
        print(e)
        return (
            {
                "state": "FAILED",
                "message": """UNABLE TO GET THE NEEDED PARAMETERS
                                            TO RUN THE CLOUD FUNCTION""",
            },
            400,
        )
