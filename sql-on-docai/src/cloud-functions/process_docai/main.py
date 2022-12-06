import os
from google.cloud import documentai_v1 as documentai
from google.cloud import storage
import re
import urllib.request
import json
from google.cloud import resourcemanager_v3

def get_project_number(project_id):
    """Given a project id, return the project number"""
    # Create a client
    client = resourcemanager_v3.ProjectsClient()
    # Initialize request argument(s)
    request = resourcemanager_v3.SearchProjectsRequest(query=f"id:{project_id}")
    # Make the request
    page_result = client.search_projects(request=request)
    # Handle the response
    for response in page_result:
        if response.project_id == project_id:
            project = response.name
            return project.replace('projects/', '')

def get_gcs_file(uri):
    matches = re.match("gs://(.*?)/(.*)", uri)
    if matches:
        bucket_name, object_name = matches.groups()
        bucket = storage_client.get_bucket(bucket_name)
        gcs_file = bucket.get_blob(object_name)
        file_blob = gcs_file.download_as_bytes()
        return file_blob

url = "http://metadata.google.internal/computeMetadata/v1/project/project-id"
req = urllib.request.Request(url)
req.add_header("Metadata-Flavor", "Google")
project_id = urllib.request.urlopen(req).read().decode()

project_number = get_project_number(project_id)

storage_client = storage.Client()

def get_doc(request):
    
    request_json = request.get_json(silent=True)
    
    replies = []
    calls = request_json['calls']
   
    for call in calls:
        uri = call[0]
        content_type = call[1]
        location = call[2]
        processor_id = call[3]
        
        print("Uri:",uri)
        print("Content:",content_type)
        print("Processor_id:",processor_id)
        print("Location:", location)

        processor = f"projects/{project_number}/locations/{location}/processors/{processor_id}"
        accepted_file_types = ["application/pdf","image/jpg","image/png","image/gif","image/tiff","image/jpeg","image/tif","image/webp","image/bmp"]
        opts = {"api_endpoint": f"{location}-documentai.googleapis.com"}
        docai_client = documentai.DocumentProcessorServiceClient(client_options=opts)

        if content_type in accepted_file_types:
            file = get_gcs_file(uri)
            raw_document = documentai.RawDocument(content=file, mime_type=content_type)
            request = documentai.ProcessRequest(name=processor, raw_document=raw_document)
            response = docai_client.process_document(request=request)
            document = response.document
            
            types = []
            raw_values = []
            normalized_values = []
            confidence = []

            print("Length:",len(document.entities))

            for entity in document.entities:
                types.append(entity.type_)
                raw_values.append(entity.mention_text)
                normalized_values.append(entity.normalized_value.text)
                confidence.append(f"{entity.confidence:.0%}")

                # Get Properties (Sub-Entities) with confidence scores
                for prop in entity.properties:
                    types.append(prop.type_)
                    raw_values.append(prop.mention_text)
                    normalized_values.append(prop.normalized_value.text)
                    confidence.append(f"{prop.confidence:.0%}")
                    
            
            extracted_val = { "Type": types,"Raw Value": raw_values,"Normalized Value": normalized_values,"Confidence": confidence}
            replies.append(extracted_val)    

        else:
            error_response = [{'output':'Cannot parse the file type'}]
            replies.append(error_response)
            
    return json.dumps({'replies': [json.dumps(extracts) for extracts in replies]})
