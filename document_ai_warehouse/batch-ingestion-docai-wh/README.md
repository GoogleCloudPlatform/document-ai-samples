# Quickstart Guide to Batch Upload Documents into the DocAi Warehouse

<!-- TOC -->
* [Quickstart Guide to Batch Upload Documents into the DocAi Warehouse](#quickstart-guide-to-batch-upload-documents-into-the-docai-warehouse)
  * [Introduction](#introduction)
    * [use Cases](#use-cases)
    * [Limitations:](#limitations-)
  * [Prerequisites](#prerequisites)
    * [Prepare Python Environment](#prepare-python-environment)
    * [Provision DocAI Warehouse (`DOCAI_WH_PROJECT_ID`)](#provision-docai-warehouse--docaiwhprojectid-)
    * [Prepare GCS Bucket with Data (`DATA_PROJECT_ID`)](#prepare-gcs-bucket-with-data--dataprojectid-)
    * [Create processor for extracting text data from the PDF forms (`DOCAI_PROJECT_ID`)](#create-processor-for-extracting-text-data-from-the-pdf-forms--docaiprojectid-)
    * [Set Env Variables](#set-env-variables)
    * [Cross-Org Access (Only when required)](#cross-org-access--only-when-required-)
  * [Setup](#setup)
  * [Execution](#execution)
    * [Batch Upload](#batch-upload)
    * [Generate draft document schema using DocAi output of the CDE Processor](#generate-draft-document-schema-using-docai-output-of-the-cde-processor)
    * [Upload document schema to DocAI WH](#upload-document-schema-to-docai-wh)
    * [Batch Upload using document schema (With properties extraction) and CDE processor](#batch-upload-using-document-schema--with-properties-extraction--and-cde-processor)
  * [Troubleshooting](#troubleshooting)
    * [Error 403 IAM_PERMISSION_DENIED Permission Denied](#error-403-iampermissiondenied-permission-denied)
    * [Generate draft document schema using DocAi output of the CDE Processor](#generate-draft-document-schema-using-docai-output-of-the-cde-processor-1)
    * [Upload document schema to DocAI WH](#upload-document-schema-to-docai-wh-1)
    * [Batch Upload using document schema (With properties extraction) and CDE processor](#batch-upload-using-document-schema--with-properties-extraction--and-cde-processor-1)
  * [Troubleshooting](#troubleshooting-1)
    * [Error 403 IAM_PERMISSION_DENIED Permission Denied](#error-403-iampermissiondenied-permission-denied-1)
<!-- TOC -->

## Introduction
This is a utility that allows a batch upload of Folders/Files stored in GCS bucket into the Document WH using Processor to extract structured data.
Supported Features:
- Generation of the document schema based on the DocAI output.
- Filling in document properties using schema and DocAI output.
- Batch upload using GCS uri as an input (can be in separate project different from the DocAI WH project) while preserving the original folder structure.
- There is no limit on 15 pages per document, since asynchronous batch processing is used by the DocAI parser.
- When folder contains high amount of documents, it might take a while for a batch operation to complete.
  - When using Cloud Shell, this might time out on the session.
- Processors can be in a separate project different from the DocAI WH project.
- Also, you are able to batch upload large amounts of documents with up to 200 pages, either using an OCR parser, or existing pre-trained or custom trained processors, along with the extracted properties.


### use Cases
There are two main use Cases:

1. Batch upload of PDF documents containing Plain text (using OCR parser).
   * In this case the document schema will not contain any properties.
2. Batch upload of PDF forms containing special properties (using special parsers, such as pre-trained Invoice parser, ir Custom Trained CDE Parser)
   * In this situation the document schema with properties has to be created based on the Parser.
   * While schema could be auto-magically created for you with the best effort and uploaded seamlessly in the upload operation, it is recommended however to use this utility to also: 
   
     - Generate the DocAI WH document schema based on the DocAI processor output.
     - Inspect the generated schema and correct the types if necessary.
     - Upload the generated schema to the DocAI WH.
     - Upload documents using verified uploaded schema.

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
    - Enable question and answering to help find documents using GenAI.
    - Skip Initialization - Create a document schema (Click Next)
    - You can skip Optional step for Service Account creation and ski and click Next
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

As an example, you could use `sample_data/fake_invoices`:

```shell 
gcloud storage buckets create gs://${DATA_PROJECT_ID}-data --project  $DATA_PROJECT_ID
gsutil -m cp -r sample_data/fake_invoices/*  gs://${DATA_PROJECT_ID}-data/invoices/
```


### Create processor for extracting text data from the PDF forms (`DOCAI_PROJECT_ID`)
- You can either use same project as used for DocAI Warehouse/Data Project, create a new one, or use an existing Project with the trained processors. 
- Create a processor to parse the documents, such as OCR processor. 
  - If you are following with the sample above with fake invoices, best would be to use pre-trained Invoice Parser.
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


### Batch Upload
- Works well for Large (<200 pages) pdf documents, that could be loaded into DocAI WH with text information used for GenAI search.
- Preserves the original directory structure (with sub-folders) on gcs.
- When `schema_id` is not provided, will create new schema based in the DocAI output of the first document in the batch. This works well for the OCR parser (since schema is empty).
- For other parsers, it is recommended to follow these steps:
  - [Generate document schema](#generate-draft-document-schema-using-docai-output-of-the-cde-processor)
  - manually inspect it locally and correct the document types
  - [Upload document schema](#upload-document-schema-to-docai-wh), and then 
  - Use created `schema_id` as an input to the Batch upload below.

> NB! processor `PROCESSOR_ID` must be inside the `DOCAI_PROJECT_ID` (when multiple projects are used)

```shell
export PROCESSOR_ID=<PROCESSOR_ID>
source SET
python load_docs.py -d gs://<PATH-TO-DIR> [-n <NAME-OF-THE-ROOT-FOLDER] [-o] [-s schema_id] [--flatten]
```
Parameters:
```shell
-d -  Path to the GCS storage folder, containing data with PDF documents to be loaded. All original structure of sub-folders will be preserved.
-n -  (optional) `Name` of the root folder inside DW to upload the documents/folders. When omitted, will the name of the folder/bucket being loaded from.
-s -  (optional) `Schema_id` to be used when the uploading document. By default application relies on the processor.display_name and searches for schema with that name. 
-o -  (optional) When set, will overwrite files if already exist. By default, will skip files based on the file path and file name.
--options - (optional) - When set (by default), will automatically fill in document properties using schema options.
--flatten - (optional) - When set, will flatten sub-directories. Otherwise (by default) preserves the original structure.
```

Example: Batch Upload with Fake invoices (will generate document schema):
```shell
export PROCESSOR_ID=<INVOICE_PROCESSOR_ID>
source SET
python load_docs.py -d gs://${DATA_PROJECT_ID}-data/invoices -n invoices
```

Example: Batch Upload with Fake invoices (will use existing document schema `MY_SCHEMA_ID`, a result of generate/verify/upload steps explained below):
```shell
export PROCESSOR_ID=<INVOICE_PROCESSOR_ID>
source SET
python load_docs.py -d gs://${DATA_PROJECT_ID}-data/invoices -n invoices -s <MY_SCHEMA_ID>
```


### Generate draft document schema 
- Using sample pdf document and the DocAI output, document schema is generated and saved locally with document properties.
- The schema should be manually verified for the correctness of property types and then uploaded to document WH in the following step below.
- `display_name` of the generated document schema  corresponds to the display name of the processor.

> NB! `PATH_TO_PDF` must be inside the `DATA_PROJECT_ID`
> CDE processor `PROCESSOR_ID` must be inside the `DOCAI_PROJECT_ID`

```shell
export PROCESSOR_ID=<PROCESSOR_ID>
source SET
python generate_schema.py -f gs://<PATH-TO-PDF> 
```
Parameters:
```shell
-f -  Path to the GCS uri PDF for entity extraction used with PROCESSOR_ID, so that entities are used to generate the document schema.
-n -  (optional) When specified, schema display name. Otherwise will use processor display name.
```

Example to generate schema for the fake invoice with assigned shcema display_name:
```shell
export PROCESSOR_ID=<INVOICE_PROCESSOR_ID>
python generate_schema.py -f gs://${DATA_PROJECT_ID}-data/invoices/Invoice1.pdf -n my_invoice
````

Sample output:
```shell
batch_extraction - Calling Processor API for 1 document(s) batch_extraction - Calling DocAI API for 1 document(s)  using inv processor type=INVOICE_PROCESSOR, path=projects/978098347395/locations/us/processors/18849599a3ece785
batch_extraction - Waiting for operation projects/978098347395/locations/us/operations/6041130884555864540 to complete...
batch_extraction - Elapsed time for operation 22 seconds
batch_extraction - Handling DocAI results for gs://...-data/invoices/Invoice1.pdf using process output gs://...-docai-output/6041130884555864540/0
Generated /Users/.../document-ai-samples/document_ai_warehouse/batch-ingestion-docai-wh/schema_files/my_invoice.json with document schema for gs://...-data/invoices/Invoice1.pdf
```

Now, open and verify `schema_files/my_invoice.json`.

### Upload document schema to DocAI WH
After you have generated and verified  document schema, it is time to upload it to the DocAI WH.
To avoid confusions, if there is already existing schema with same display_name, operation will be skipped (unless -o option is used).
Please note, that overwriting with `-o` option is not possible, if there are already existing documents using that schema. You will need to first remove all the existing documents using that schema.

```shell
source SET
python upload_schema.py -f schema_files/<PROCESSOR_NAME>.json
```
Parameters:
```shell
-f -  Path to JSON file stored locally with the document schema.
-o -  (optional) When set, will overwrite existing schema with the same display name, otherwise (default) will skip upload action. However if there are already files using that schema, the application would not be able to overwrite schema and will skip.
```
Example:
```shell
python upload_schema.py -f schema_files/my_invoice.json
````

Sample output:
```shell
create_document_schema - Created document schema with display_name = my_invoice and schema_id = 0tv9nva44dnf0
```

Note down schema_id, so you can use it for the batch upload:

```shell
python load_docs.py -d gs://${DATA_PROJECT_ID}-data/invoices -n invoices2 -s <MY_SCHEMA_ID>
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


Expected Output:
```shell
ROLE
ROLE: roles/contentwarehouse.admin
ROLE: roles/contentwarehouse.documentAdmin
ROLE: roles/documentai.apiUser
ROLE: roles/logging.logWriter
ROLE: roles/documentai.viewer
```

