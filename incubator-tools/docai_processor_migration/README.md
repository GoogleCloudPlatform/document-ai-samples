# Purpose and Description

The python script aims to automate the process of migrating a Document AI processor from one project to another by handling tasks such as importing the data, creating the schema, and automatically training the processor using the dataset from the source project.

# Input Details
* **SOURCE_PROCESSOR_NAME** - This involves source project_id and source processor_id.  
    * Ex: projects/**Project_number**/locations/us/processors/**Processor_ID**
* **DESTINATION_PROJECT_NUMBER** - This contains the project number to which the processor needs to be moved. 
* **DESTINATION_PROCESSOR_LOCATION** - This indicates the processor destination location. 
* **DESTINATION_PROCESSOR_DATASET_GCS_URI** - The GCS bucket path which is used for the destination processor dataset, automatically created if it does not exist.
* **SOURCE_EXPORTED_DATASET_GCS_URI** - This is the GCS bucket path where the dataset from the source processor has been exported. Ensure that you export your dataset via the user interface and then input its path here.
* **DESTINATION_EXPORTED_DATASET_GCS_URI** - This is the GCS bucket path where the dataset from the source processor will be copied over to the destination project. Simply provide an empty bucket path here.

**NOTE**
* Allowed path example: _gs://bucket_
* Not Allowed path example: _gs://bucket/sub_folder_

# Output Details
Upon successful execution of `migrate_processor` function, you can find the url to UI of migrated processor like this https://console.cloud.google.com/ai/document-ai/locations/us/processors/xxxx-xxxx-xxxx/dataset?project=xxxx-xxxx-xxxx in printed-output details