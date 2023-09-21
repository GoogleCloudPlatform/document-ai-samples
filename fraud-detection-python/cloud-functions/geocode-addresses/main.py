# mypy: disable-error-code="1"
"""
Sends address data from Invoices to Geocode API and writes to BigQuery
"""
import base64
import json
import os
from urllib.parse import urlencode

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import bigquery
import requests

DATASET_NAME = "invoice_parser_results"
TABLE_NAME = "geocode_details"

bq_client = bigquery.Client()


def write_to_bq(dataset_name, table_name, geocode_response_dict):
    """
    Write Geocode Data to BigQuery
    """
    dataset_ref = bq_client.dataset(dataset_name)
    table_ref = dataset_ref.table(table_name)
    row_to_insert = []
    row_to_insert.append(geocode_response_dict)

    json_data = json.dumps(row_to_insert, sort_keys=False)
    json_object = json.loads(json_data)

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
    )

    try:
        job = bq_client.load_table_from_json(
            json_object, table_ref, job_config=job_config
        )
        result = job.result()  # Waits for table load to complete.
        print(result)
    except GoogleAPICallError as ex:
        print(ex)


# pylint: disable=unused-argument
def process_address(event, context):
    """Triggered from a message on a Cloud Pub/Sub topic.
    Args:
    event (dict): Event payload.
    context (google.cloud.functions.Context): Metadata for the event.
    """
    pubsub_message = base64.b64decode(event["data"]).decode("utf-8")
    message_dict = json.loads(pubsub_message)
    query_address = message_dict.get("entity_text")
    geocode_dict = {}
    geocode_dict["input_file_name"] = message_dict.get("input_file_name")
    geocode_dict["entity_type"] = message_dict.get("entity_type")
    geocode_dict["entity_text"] = query_address
    geocode_response_dict = extract_geocode_info(query_address)
    geocode_dict.update(geocode_response_dict)
    print(geocode_dict)

    write_to_bq(DATASET_NAME, TABLE_NAME, geocode_dict)


def extract_geocode_info(query_address, data_type="json") -> dict:
    """
    Extract Geocode Data from Google Maps API
    """
    geocode_response_dict = {}
    endpoint = f"https://maps.googleapis.com/maps/api/geocode/{data_type}"
    api_key = os.environ.get("API_key")
    params = {"address": query_address, "key": api_key}
    url_params = urlencode(params)
    try:
        request = requests.get(endpoint, params=url_params)
        results = request.json()["results"][0]
        location = results["geometry"]["location"]

        geocode_response_dict["place_id"] = results["place_id"]
        geocode_response_dict["formatted_address"] = results["formatted_address"]
        geocode_response_dict["lat"] = str(location.get("lat"))
        geocode_response_dict["lng"] = str(location.get("lng"))

    except requests.exceptions.RequestException as ex:
        print(ex)

    return geocode_response_dict
