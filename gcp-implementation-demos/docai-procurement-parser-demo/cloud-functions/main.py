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
gcs_output_uri = f"gs://{project_id}-output-petsmart-invoices"
gcs_output_bucket_name = f"{project_id}-output-petsmart-invoices"
gcs_archive_bucket_name = f"{project_id}-archived-petsmart-invoices"
gcs_rejected_bucket_name = f"{project_id}-rejected-petsmart-files"
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
        bigquery.SchemaField("currency", "STRING"),
        bigquery.SchemaField("invoice_id", "STRING"),
        bigquery.SchemaField("net_amount", "STRING"),
        bigquery.SchemaField("remit_to_name", "STRING"),
        bigquery.SchemaField("remit_to_address", "STRING"),        
        bigquery.SchemaField("invoice_date", "DATE"),        
        bigquery.SchemaField("supplier_address", "STRING"),        
        bigquery.SchemaField("supplier_city", "STRING"),
        bigquery.SchemaField("supplier_name", "STRING"),        
        bigquery.SchemaField("supplier_website", "STRING"), 
        bigquery.SchemaField("supplier_email", "STRING"), 
        bigquery.SchemaField("receiver_name", "STRING"),        
        bigquery.SchemaField("receiver_tax_id", "STRING"),
        bigquery.SchemaField("receiver_address", "STRING"),
        bigquery.SchemaField("supplier_iban", "STRING"),        
        bigquery.SchemaField("purchase_order", "STRING"),        
        bigquery.SchemaField("total_amount", "STRING"),
        bigquery.SchemaField("total_tax_amount", "STRING"),        
        bigquery.SchemaField("line_item", "STRING"),
        bigquery.SchemaField("line_item_amount", "STRING"),
        bigquery.SchemaField("line_item_description", "STRING"),
        bigquery.SchemaField("ship_from_address", "STRING"), 
        bigquery.SchemaField("ship_to_address", "STRING"),        
        bigquery.SchemaField("carrier", "STRING"),        
        bigquery.SchemaField("freight_amount", "STRING"),  
        bigquery.SchemaField("delivery_date", "DATE"), 
        bigquery.SchemaField("due_date", "DATE"),        
        bigquery.SchemaField("vat", "STRING"),
        bigquery.SchemaField("vat_tax_amount", "STRING"),        
        bigquery.SchemaField("payment_terms", "STRING"),
        bigquery.SchemaField("line_item_product_code", "STRING")
    ])
 
   job = bq_client.load_table_from_json(json_object, table_ref, job_config=job_config)
   error = job.result()  # Waits for table load to complete.
   
  
 
def process_receipt(event, context):
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
