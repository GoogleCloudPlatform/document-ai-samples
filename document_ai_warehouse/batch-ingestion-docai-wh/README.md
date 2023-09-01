# Quickstart Guide to Batch Upload Documents into the DocAi Warehouse

<!-- TOC -->
* [Quickstart Guide to Batch Upload Documents into the DocAi Warehouse](#quickstart-guide-to-batch-upload-documents-into-the-docai-warehouse)
  * [Introduction](#introduction)
    * [Limitations:](#limitations-)
  * [Prerequisites](#prerequisites)
    * [Prepare Python Environment](#prepare-python-environment)
    * [Provision DocAI Warehouse (`DOCAI_WH_PROJECT_ID`)](#provision-docai-warehouse--docaiwhprojectid-)
    * [Prepare GCS Bucket with Data (`DATA_PROJECT_ID`)](#prepare-gcs-bucket-with-data--dataprojectid-)
    * [Create OCR processor for extracting text data from the PDF forms (`DOCAI_PROJECT_ID`)](#create-ocr-processor-for-extracting-text-data-from-the-pdf-forms--docaiprojectid-)
    * [Set Env Variables](#set-env-variables)
    * [Cross-Org Access (Only when required)](#cross-org-access--only-when-required-)
  * [Setup](#setup)
  * [Execution](#execution)
    * [Batch directory upload using OCR Parser (No Properties Extraction)](#batch-directory-upload-using-ocr-parser--no-properties-extraction-)
    * [Generate draft document schema using DocAi output of the CDE Processor](#generate-draft-document-schema-using-docai-output-of-the-cde-processor)
    * [Upload document schema to DocAI WH](#upload-document-schema-to-docai-wh)
    * [Batch Upload using document schema (With properties extraction) and CDE processor](#batch-upload-using-document-schema--with-properties-extraction--and-cde-processor)
  * [Troubleshooting](#troubleshooting)
    * [Error 403 IAM_PERMISSION_DENIED Permission Denied](#error-403-iampermissiondenied-permission-denied)
<!-- TOC -->

## Introduction
This is a utility that allows a batch upload of Folders/Files stored in GCS bucket into the Document WH using Processor to extract structured data.
Supported Features:
- Generation of the document schema based on the DocAI output.
- Filling in document properties using schema and DocAI output.
- Batch upload using GCS uri as an input (can be in different project) and preserving original structure with subdirectories.
- There is no limit on 15 pages per document, since asynchronous batch processing is used by the DocAI parser.
- When folder contains high amount of documents, it might take a while for a batch operation to complete.
  - When using Cloud Shell, this might time out on the session.
- Processors can be in a different project.

For example, you can use an existing pre-trained processor, such as Invoice parser or CDE, and generate document schema inside DocAI WH. The step, that otherwise is done manually.
Also, you are able to batch upload large amounts of documents with up to 200 pages, either using an OCR parser, or existing pre-trained or custom trained processors, along with the extracted properties.
~~~~
### Limitations:
- Only PDF files are handled.
- There is a maximum of 200 pages per document.

## Prerequisites

### Prepare Python Environment

```shell
cd document_ai_warehouse/batch-ingestion-docai-wh
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

### Provision DocAI Warehouse (`DOCAI_WH_PROJECT_ID`)
- Create GCP Project wth a linked Billing Account
- Enable [Document AI Warehouse API](https://pantheon.corp.google.com/apis/library/contentwarehouse.googleapis.com) in your Google Cloud project and click Next.

- Provision the Instance:
    - For now, use `Universal Access: No document level access control` for the ACL modes in DocAI Warehouse and click Provision, then Next.
    - Provision DocAI warehouse Instance [Document AI Warehouse console](https://documentwarehouse.cloud.google.com) (which is external to the Google Cloud console).
    - You can skip Optional step for Service Account creation  and click Next
    - Click Done
- Follow link to Configure the Web Application:
    - Select Location (same as the location of the CDA and DocAI processors), Select Access Control (ACL) mode same as in the step before.
    - Click Create
    - Click "Search" in the top right corner -> This is where all documents will appear after the script execution is finished. 

### Prepare GCS Bucket with Data (`DATA_PROJECT_ID`)
- You can either use same project as created in previous step, or a different project.
- Upload pdf forms that you want to ingest into DocumentAI warehouse into the GCS bucket.
  - Currently, only PDF documents are supported.
- GCS bucket can have hierarchical structure, which will be preserved when loading into the DocAI Warehouse.



### Create processor for extracting text data from the PDF forms (`DOCAI_PROJECT_ID`)
- You can either use same project as used for DocAI Warehouse/Data Project, create a new one, or use an existing Project with the trained processors. 
- Create a processor to parse the documents, such as OCR processor. 
- Note down Processor ID.



### Set Env Variables
Set the following env variables: 

```shell
export PROJECT_ID=     # This is the default ID for all Projects if you want to have all in the same project

# Otherwise, manually setup the following: 
export DOCAI_WH_PROJECT_ID=  # Project ID of the GCP Project in which DocAI WH has been provisioned
export DATA_PROJECT_ID=      # Project ID with GCS Data to be Loaded
export DOCAI_PROJECT_ID=     # Project ID of the GCP Project with DocAI Processor used for document parsing
```

### Cross-Org Access (Only when required)
In case if your projects are under different organizations, you need to modify `constraints/iam.allowedPolicyMemberDomain` policy constraint and set it to `Allowed All`:

```shell
gcloud org-policies reset constraints/iam.allowedPolicyMemberDomains --project=$DOCAI_WH_PROJECT_ID
gcloud org-policies reset constraints/iam.allowedPolicyMemberDomains --project=$DATA_PROJECT_ID
gcloud org-policies reset constraints/iam.allowedPolicyMemberDomains --project=$DOCAI_PROJECT_ID
```


## Setup 
* The setup step takes care of the required access permissions and roles (user must have owner rights to the projects and be able to modify org policy and add IAM permissions).
* As the output the Service Account Key  (`$KEY_PATH`) is generated in the current directory, which is used in the execution step. 
* Whenever setup is changed (different `DATA_PROJECT_ID`), env variables need to be updated and below utility needs to be run again.
* 
```shell
./setup_docai_wh.sh
```

## Execution


### Batch directory upload using OCR Parser (No Properties Extraction)
- Works well for Large (<200 pages) pdf documents, that could be loaded into DocAI WH with text information used for GenAI search.
- Preserves the original directory structure (with sub-folders) on gcs.

> NB! OCR processor `PROCESSOR_ID` must be inside the `DOCAI_PROJECT_ID`

```shell
export PROCESSOR_ID=<OCR_PROCESSOR_ID>
source SET
GOOGLE_APPLICATION_CREDENTIALS=${KEY_PATH} python load_docs.py -d gs://<PATH-TO-FOLDER> [-n <NAME-OF-THE-ROOT-FOLDER] [-o] [--options] [-s schema_id]
```
Parameters:
```shell
-d -  Path to the GCS storage folder, containing data with PDF documents to be loaded. All original structure of sub-folders will be preserved.
-n -  (optional) `Name` of the root folder inside DW to upload the documents/folders. When omitted, will the name of the folder/bucket being loaded from.
-s -  (optional) `Schema_id` to be used when the uploading document. By default application relies on the processor.display_name and searches for schema with that name. 
-o -  (optional) When set, will overwrite files if already exist. By default, will skip files based on the file path and file name.
--options - (optional) - When set, will automatically fill in document properties using schema options. Otherwise (by default) uses default schema with no options. Can be used with CDE processor only and valid existing corresponding schema.
--flatten - (optional) - When set, will flatten sub-directories. Otherwise (by default) preserves the original structure.
```

Example:
```shell
GOOGLE_APPLICATION_CREDENTIALS=${KEY_PATH}  python load_docs.py -d gs://ek-cda-engine-001-um-guidelines -n UM_Guidelines
```

### Generate draft document schema using DocAi output of the CDE Processor
- Using sample document and CDE Processor  output, following command will dump a draft document schema with properties.
- The schema should be manually verified for the correctness of property types and then uploaded to document WH in the following step below.

> NB! `PATH_TO_PDF` must be inside the `DATA_PROJECT_ID`
> CDE processor `PROCESSOR_ID` must be inside the `DOCAI_PROJECT_ID`

```shell
export PROCESSOR_ID=<CDE_PROCESSOR_ID>
source SET
GOOGLE_APPLICATION_CREDENTIALS=${KEY_PATH} python generate_schema.py -f gs://<PATH-TO-PDF> 
```
Parameters:
```shell
-f -  Path to the GCS uri PDF for entity extraction used with PROCESSOR_ID, so that entities are used to generate the document schema.
```

Example:
```shell
GOOGLE_APPLICATION_CREDENTIALS=${KEY_PATH} python load_docs.py -f gs://ek-cda-engine-001-sample-forms/bsc-dme-pa-form-9.pdf
````

```shell
PROCESSOR_ID=<OCR_PROCESSOR_ID> python load_docs.py -d gs://bucket-name/um -n UM_Guidelines
```

```shell
PROCESSOR_ID=<CDE_PROCESSOR_ID> python generate_schema.py -f gs://bucket-name/bsc-forms/form1.pdf 
```

```shell
PROCESSOR_ID=<CDE_PROCESSOR_ID> python upload_schema.py -f schema_files/bsc-cde.json 
```

```shell
PROCESSOR_ID=<CDE_PROCESSOR_ID> python load_docs.py -d gs://bucket-name/bsc-forms --options -n BSC-Forms
```

Sample output:
```shell
batch_extraction - Calling Processor API for 1 document(s) batch_extraction - Calling DocAI API for 1 document(s)  using cda_extractor processor type=CUSTOM_EXTRACTION_PROCESSOR, path=projects/646417134223/locations/us/processors/db85932341d1fac73b
batch_extraction - Waiting for operation projects/646417469923/locations/us/operations/15498778173307598442 to complete...
batch_extraction - Elapsed time for operation 23 seconds
batch_extraction - Handling DocAI results for gs://ek-cda-engine-001-sample-forms/forms-batch1/bsc-dme-pa-form-9.pdf using process output gs://ek-test-docwh-01-docai-output/15498778173307598442/0
Generated /Users/xxx/document-intake-accelerator/utils/docai-wh/schema_files/cda_extractor.json with document schema for gs://ek-cda-engine-001-sample-forms/forms-batch1/bsc-dme-pa-form-9.pdf
```

### Upload document schema to DocAI WH
After you have generated and verified  document schema, it is time to upload it to the DocAI WH.
To avoid confusions, if there is already existing schema with same display_name, operation will be skipped (unless -o option is used).
Please note, that overwriting with `-o` option will not be possible, if there are already existing documents using that schema.

```shell
source SET
GOOGLE_APPLICATION_CREDENTIALS=${KEY_PATH} python upload_schema.py -f gs://<PATH-TO-JSON>.json
```
Parameters:
```shell
-f -  Path to JSON file locally with document schema.
-o -  (optional) When set, will overwrite existing schema with the same display name, otherwise (default) will skip upload action. However if there are already files using that schema, the application would not be able to overwrite schema and will skip.
```
Example:
```shell
GOOGLE_APPLICATION_CREDENTIALS=${KEY_PATH} python upload_schema.py -f /Users/xxx/document-intake-accelerator/utils/docai-wh/schema_files/cda_extractor.json
````


### Batch Upload using document schema (With properties extraction) and CDE processor
- `display_name` of the document schema generated and uploaded on the previous step corresponds to the display name of the processor.
- If you have not changed json file before uploading the schema, when using same PROCESSOR_ID, everything will work out-of the box.
- If you have changed `display_name` of the schema prior to uploading it, you will need to provide `schema_id` as input parameter.

```shell
source SET
PROCESSOR_ID=<CDE_PROCESSOR> GOOGLE_APPLICATION_CREDENTIALS=${KEY_PATH} python load_docs.py -d gs://<PATH-TO-FORMS> --options -n Test-Forms 
```

When specifying schema explicitly:
```shell
PROCESSOR_ID=<CDE_PROCESSOR> GOOGLE_APPLICATION_CREDENTIALS=${KEY_PATH} python load_docs.py -d gs://<PATH-TO-PDF>.pdf --options -n Test-Forms -s schema_id
```

## Troubleshooting 
### Error 403 IAM_PERMISSION_DENIED Permission Denied

  ```403 Permission 'contentwarehouse.documentSchemas.list' denied on resource '//contentwarehouse.googleapis.com/projects/35407211402/locations/us' (or it may not exist). [reason: "IAM_PERMISSION_DENIED"```
  
**Solution**: I have noticed it takes up to ten minutes for the roles to be properly propagated to the service account.
* Make sure all rights are properly assigned:
```shell
gcloud projects get-iam-policy $DOCAI_WH_PROJECT_ID --flatten="bindings[].members" --format='table(bindings.role)' --filter="bindings.members:${SA_EMAIL}"
```

Expected Output:
```shell
ROLE
ROLE: roles/contentwarehouse.admin
ROLE: roles/contentwarehouse.documentAdmin
ROLE: roles/documentai.apiUser
ROLE: roles/logging.logWriter
ROLE: roles/documentai.viewer
```

[//]: # (````shell)

[//]: # (gcloud projects get-iam-policy $DOCAI_PROJECT_ID --flatten="bindings[].members" --format='table&#40;bindings.role&#41;' --filter="bindings.members:${SA_EMAIL}")

[//]: # (````)
[//]: # (```shell)

[//]: # (  gcloud projects get-iam-policy $DATA_PROJECT_ID --flatten="bindings[].members" --format='table&#40;bindings.role&#41;' --filter="bindings.members:${SA_EMAIL}")

[//]: # (```)

[//]: # (Expected Output:)

[//]: # (```shell)

[//]: # (ROLE)

[//]: # (roles/storage.objectViewer)

[//]: # (```)
