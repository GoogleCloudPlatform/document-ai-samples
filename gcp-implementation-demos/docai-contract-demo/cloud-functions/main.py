import base64
import re
import os
import json
from datetime import datetime
from google.cloud import bigquery
from google.cloud import documentai_v1beta3 as documentai
from google.cloud import storage
from google.cloud import pubsub_v1
 
# Read environment variables
project_id = os.environ.get('GCP_PROJECT')
location = os.environ.get('PARSER_LOCATION')
processor_id = os.environ.get('PROCESSOR_ID')
timeout = int(os.environ.get('TIMEOUT'))
dataset_name = os.environ.get('BQ_DATASET_NAME')
table_name = os.environ.get('BQ_TABLE_NAME')

# Set variables
address_substring = "address"
gcs_output_uri = f"gs://{project_id}-output-acme-contracts"
gcs_output_bucket_name = f"{project_id}-output-acme-contracts"
gcs_archive_bucket_name = f"{project_id}-archived-acme-contracts"
gcs_rejected_bucket_name = f"{project_id}-rejected-acme-contracts"
name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"
accepted_file_types = ["application/pdf","image/jpg","image/png","image/gif","image/tiff","image/jpeg","image/tif","image/webp","image/bmp"]

# Create GCP clients
docai_client = documentai.DocumentProcessorServiceClient()
storage_client = storage.Client()
bq_client = bigquery.Client()
pub_client = pubsub_v1.PublisherClient()
 
def write_to_bq(dataset_name, table_name, entities_extracted_dict):
   dataset_ref = bq_client.dataset(dataset_name)
   table_ref = dataset_ref.table(table_name)

   row_to_insert =[]
   row_to_insert.append(entities_extracted_dict)
   json_data = json.dumps(row_to_insert, sort_keys=False)

   # Convert to a JSON Object
   json_object = json.loads(json_data)
  
   job_config = bigquery.LoadJobConfig(source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON, ignore_unknown_values=True,
   schema=[
        bigquery.SchemaField("document_name", "STRING"),
        bigquery.SchemaField("agreement_date", "DATE"),        
        bigquery.SchemaField("arbitration_venue", "STRING"),        
        bigquery.SchemaField("confidentiality_clause", "STRING"),
        bigquery.SchemaField("effective_date", "DATE"), 
        bigquery.SchemaField("expiration_date", "DATE"),        
        bigquery.SchemaField("governing_law", "STRING"),
        bigquery.SchemaField("indemnity_clause", "STRING"),        
        bigquery.SchemaField("initial_term", "STRING"),
        bigquery.SchemaField("litigation_venue", "STRING"),
        bigquery.SchemaField("notice_to_terminate_renewal", "STRING"),
        bigquery.SchemaField("non_compete_clause", "STRING"),
        bigquery.SchemaField("parties", "STRING"),
        bigquery.SchemaField("renewal_term", "STRING")
    ])
 
   job = bq_client.load_table_from_json(json_object, table_ref, job_config=job_config)
   error = job.result()  # Waits for table load to complete.
   
  
 
def process_contracts1(event, context):
   gcs_input_uri = 'gs://' + event['bucket'] + '/' + event['name']

   if event['contentType'] in accepted_file_types:
       input_config = documentai.types.document_processor_service.BatchProcessRequest.BatchInputConfig(gcs_source=gcs_input_uri, mime_type=event['contentType'])
       # Where to write results
       output_config = documentai.types.document_processor_service.BatchProcessRequest.BatchOutputConfig(gcs_destination=gcs_output_uri)
 
       request = documentai.types.document_processor_service.BatchProcessRequest(
           name=name,
           input_configs=[input_config],
           output_config=output_config,
       )
 
       operation = docai_client.batch_process_documents(request)
 
       # Wait for the operation to finish
       operation.result(timeout=timeout)
       print("Entities extracted from DocAI.")
 
       #match = re.match(r"gs://([^/]+)/(.+)", destination_uri)
       #output_bucket = match.group(1)
       #prefix = match.group(2)
      
       #Get a pointer to the GCS bucket where the output will be placed
       bucket = storage_client.get_bucket(gcs_output_bucket_name)
      
       blob_list = list(bucket.list_blobs())
 
       for blob in blob_list:
           # Download the contents of this blob as a bytes object.
           if ".json" not in blob.name:
                print(f"Skipping non-supported file type: {blob.name}")
           else:      
                # Getting ready to read the output of the parsed document - setting up "document"
                blob_as_string = blob.download_as_string()
                document = documentai.types.Document.from_json(blob_as_string)
      
                # Reading all entities into a dictionary to write into a BQ table
                entities_extracted_dict = {}
                #entities_extracted_dict['input_file_name'] = input_filename

                for entity in document.entities:
                    entity_type = str(entity.type_)
                    # TODO: this might not be working
                    if '/' in entity_type:
                        entity_type = entity_type.replace("/","_")
                        print("New entity type: ", entity_type)

                    #Normalize date format in case the entity being read is a date
                    if "date" in entity_type:
                      entity_text = entity.normalized_value.text
                      entities_extracted_dict[entity_type] = entity_text
                    else:
                      entity_text = str(entity.mention_text)
                      entities_extracted_dict[entity_type] = entity_text

                print("Writing to BQ.")
                # Write the entities to BQ
                write_to_bq(dataset_name, table_name, entities_extracted_dict)
                
       # Delete the intermediate files created by the Doc AI Parser
       blobs = bucket.list_blobs()
       for blob in blobs:
            blob.delete()
       # Copy input file to archive bucket
       copy_blob(event['bucket'],gcs_archive_bucket_name, event['name'])
   else:
       print('Cannot parse the file type.')
       # move file to designated bucket if file type is not supported
       copy_blob(event['bucket'],gcs_rejected_bucket_name, event['name'])

def copy_blob(source_bucket_name, dest_bucket_name, blob_name):
    source_bucket = storage_client.bucket(source_bucket_name)
    dest_bucket = storage_client.bucket(dest_bucket_name)
    blob = source_bucket.blob(blob_name)

    source_bucket.copy_blob(blob, dest_bucket, blob_name)
    blob.delete()
    return
