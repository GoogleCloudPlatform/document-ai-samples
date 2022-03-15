import base64
import json
import os
import requests
from urllib.parse import urlencode
from google.cloud import bigquery

dataset_name = 'invoice_parser_results'
table_name = 'geocode_details'
my_schema = [
{
   "name": "input_file_name",
   "type": "STRING"
 },{
   "name": "entity_type",
   "type": "STRING"
 },{
   "name": "entity_text",
   "type": "STRING"
 },{
   "name": "place_id",
   "type": "STRING"
 },{
   "name": "formatted_address",
   "type": "STRING"
 },{
   "name": "lat",
   "type": "STRING"
 },{
   "name": "lng",
   "type": "STRING"
 }
]

bq_client = bigquery.Client()
 
def write_to_bq(dataset_name, table_name, geocode_response_dict, my_schema):
 
  dataset_ref = bq_client.dataset(dataset_name)
  table_ref = dataset_ref.table(table_name)
  row_to_insert =[]
  row_to_insert.append(geocode_response_dict)

  json_data = json.dumps(row_to_insert, sort_keys=False)
  #Convert to a JSON Object
  json_object = json.loads(json_data)
  print(json_object)
  job_config = bigquery.LoadJobConfig(schema = my_schema)
  job_config.source_format = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON

  job = bq_client.load_table_from_json(json_object, table_ref, job_config=job_config)
  error = job.result()  # Waits for table load to complete.
  print(error)
  
 
def process_address(event, context):
  """Triggered from a message on a Cloud Pub/Sub topic.
  Args:
  event (dict): Event payload.
  context (google.cloud.functions.Context): Metadata for the event.
  """
  pubsub_message = base64.b64decode(event['data']).decode('utf-8')
  #print(type(pubsub_message))
  #print(pubsub_message)
  message_dict = json.loads(pubsub_message)
  query_address = message_dict.get('entity_text')
  geocode_dict = {} 
  geocode_dict["input_file_name"] = message_dict.get('input_file_name')
  geocode_dict["entity_type"] = message_dict.get('entity_type')
  geocode_dict["entity_text"] = query_address
  geocode_response_dict = extract_geocode_info(query_address)
  geocode_dict.update(geocode_response_dict)
  print(geocode_dict)

  write_to_bq(dataset_name, table_name, geocode_dict, my_schema)
  #print(geocode_response_dict)

# Using Geocoding API 
def extract_geocode_info(query_address,data_type='json'):
   geocode_response_dict = {} 
   endpoint =f"https://maps.googleapis.com/maps/api/geocode/{data_type}"
   API_key = os.environ.get('API_key')
   params ={"address": query_address, "key":API_key}
   url_params = urlencode(params)
   #print(url_params)
   url = f"{endpoint}?{url_params}"
   print(url)
   r = requests.get(url)
   print(r.status_code)
   if r.status_code not in range(200,299):
       print('status code not in range')
       return {}
   try:
        #print(message_dict.get('entity_type'))
        #print(message_dict.get('input_filename'))
        #print(query_address)
        #geocode_response_dict["entity_type"] = message_dict.get('entity_type')
        #geocode_response_dict["input_filename"] = message_dict.get('input_filename')
        #geocode_response_dict["entity_text"] = query_address
        
        geocode_response_dict["place_id"] = r.json()['results'][0]['place_id']
        geocode_response_dict["formatted_address"] = r.json()['results'][0]['formatted_address']
        geocode_response_dict["lat"] = str(r.json()['results'][0]['geometry']['location'].get("lat"))
        geocode_response_dict["lng"] = str(r.json()['results'][0]['geometry']['location'].get("lng"))
        print(geocode_response_dict)
   except:
       pass
   return geocode_response_dict
