#  Guide to Batch Upload Documents into the DocAi Warehouse
<!-- TOC -->
* [Guide to Batch Upload Documents into the DocAi Warehouse](#guide-to-batch-upload-documents-into-the-docai-warehouse)
  * [Introduction](#introduction)
    * [Use Cases](#use-cases)
    * [Limitations](#limitations)
  * [Prerequisites](#prerequisites)
    * [Prepare Python Environment](#prepare-python-environment)
    * [Provision DocAI Warehouse](#provision-docai-warehouse)
  * [Quickstart Example](#quickstart-example)
  * [Elaborated Flow](#elaborated-flow)
    * [Setup](#setup)
      * [Set env Variables](#set-env-variables)
      * [Prepare GCS Bucket with Data](#prepare-gcs-bucket-with-data)
      * [Create Processor](#create-processor)
      * [Cross-Org Access (Only when required)](#cross-org-access--only-when-required-)
    * [Provision Infrastructure and Set Access Rights](#provision-infrastructure-and-set-access-rights)
    * [Execution](#execution)
      * [Generate Draft Document Schema](#generate-draft-document-schema)
      * [Upload Document Schema to DocAI WH](#upload-document-schema-to-docai-wh)
      * [Batch Document Ingestion](#batch-document-ingestion)
      * [Delete Document Schema](#delete-document-schema)
  * [Troubleshooting](#troubleshooting)
    * [Error 403 IAM_PERMISSION_DENIED Permission Denied](#error-403-iampermissiondenied-permission-denied)
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


### Use Cases
There are two main use Cases:

1. Batch upload of PDF documents containing Plain text (using OCR parser).
   * In this case the document schema will not contain any properties.
2. Batch upload of PDF forms containing special properties (using special parsers, such as pre-trained Invoice parser, or custom trained CDE Parser)
   * In this situation the document schema with properties has to be created based on the DocAI output.
   * While schema could be auto-magically created for you with the best effort and uploaded seamlessly in the upload operation, it is recommended to follow these steps for best accuracy:  
     - Generate the DocAI WH document schema based on the DocAI processor output.
     - Inspect the generated schema and correct the types if necessary.
     - Upload the generated schema to the DocAI WH.
     - Upload documents using verified uploaded schema.

### Limitations
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

### Provision DocAI Warehouse
- Create GCP Project wth a linked Billing Account.
- Enable [Document AI Warehouse API](https://pantheon.corp.google.com/apis/library/contentwarehouse.googleapis.com) in your Google Cloud project and click Next.

- Provision the Instance:
  - For now, use `Universal Access: No document level access control` for the ACL modes in DocAI Warehouse and click Provision, then Next.
  - Enable question and answering to help find documents using GenAI.
  - Skip Initialization - Create a document schema (Click Next)
  - Skip Service Account creation  (Click Next)
  - Click Done

## Quickstart Example

For the Quick start demo you will be using single GCP project, DocAI WH, Invoice parser and sample invoices.

1. Set env variable:
```shell
export PROJECT_ID= 
```

2. Upload sample data: 

```shell 
gcloud storage buckets create gs://${PROJECT_ID}-data --project  $PROJECT_ID
gsutil -m cp -r sample_data/invoices/*  gs://${PROJECT_ID}-data/invoices/
```

3. Create DocAI Invoice parser: go to [GCP DocAI page](https://console.cloud.google.com/ai/document-ai/processors) and create [Invoice processor](https://cloud.google.com/document-ai/docs/processors-list#processor_invoice-processor).

Set processor ID:
```shell
export PROCESSOR_ID=
```

4. Run the setup to create all required infrastructure:
```shell
./setup_docai_wh.sh
```

5. Load all required env variables into the shell:

```shell
source SET
```
5. Generate Document Schema using sample invoice. Generated schema will be of the same name as the invoice parser you created:
```shell
python generate_schema.py -f gs://${PROJECT_ID}-data/invoices/Invoice1.pdf -sn my_invoice
```

6. Open up the `schema_files/my_invoice.json` file  to get familiar with the structure. For this example, schema generated is correct, but it is not always a case.

7. Upload generated schema:
```shell
python upload_schema.py -f schema_files/my_invoice.json
```

8. Do the batch upload using the created and verified schema:
```shell
python load_docs.py -d gs://${PROJECT_ID}-data/invoices -n invoices -sn my_invoice
```

9. Since for this demo schema is correctly generated out-of-the box, we could also have skipped steps 5-7.
- You can run following command to see how for the generated schema, processor name will be used
- Use --overwrite option, since files are already there, they have to be overwritten (using different schema):
```shell
python load_docs.py -d gs://${PROJECT_ID}-data/invoices -n invoices2  --overwrite
```

Below you will see more details explained and more options available.~~~~

## Detailed Instructions
### Setup
#### Set env Variables
In the simplest case, you will need to create only one GCP Project `PROJECT_ID` to host following resources: 
- DocAI Warehouse Instance - `PROJECT_ID`
- Bucket with the PDF Documents - `PROJECT_ID`
- DocAI Processor(s) - `PROJECT_ID`


However, in some cases you want to keep everything in different projects or maybe you already have your production Pre-trained processor in one project and data ingested into another project. In that case, you will be working with three different projects: 
- DocAI Warehouse Instance - `DOCAI_WH_PROJECT_ID`
- Bucket with the PDF Documents - `DATA_PROJECT_ID`
- DocAI Processor(s) - `DOCAI_PROJECT_ID`

based on the situation, set the env variables accordingly:

```shell
export PROJECT_ID=     # This is the default ID for all Projects if you want to have all in the same project

# Otherwise, manually setup the following: 
export DOCAI_WH_PROJECT_ID=  # Project ID of the GCP Project in which DocAI WH has been provisioned
export DATA_PROJECT_ID=      # Project ID with GCS Data to be Loaded
export DOCAI_PROJECT_ID=     # Project ID of the GCP Project with DocAI Processor used for document parsing
```

#### Prepare GCS Bucket with Data 
- You can either use same single project (`PROJECT_ID`), or a different GCP project (`DATA_PROJECT_ID`)  wth a linked Billing Account.
- Upload pdf forms that you want to ingest into DocumentAI warehouse into the GCS bucket.
  - Currently, only PDF documents are supported.
- GCS bucket can have hierarchical structure, which will be preserved when loading into the DocAI Warehouse.


#### Create Processor 
- You can either use same single project (`PROJECT_ID`), or a different GCP project (`DOCAI_PROJECT_ID`)  wth a linked Billing Account.
- It could be an existing Project with the trained processor(s) or, 
- Create a processor to parse the documents, such as an OCR processor (to extract text data) or CDE processor (trained for the custom forms) or use one of the pre-trained processors, such as Invoice parser. 
- Note down Processor ID.


#### Cross-Org Access (Only when required)
In case if your projects are under different organizations, you need to modify `constraints/iam.allowedPolicyMemberDomain` policy constraint and set it to `Allowed All`:

```shell
gcloud org-policies reset constraints/iam.allowedPolicyMemberDomains --project=$DOCAI_WH_PROJECT_ID
gcloud org-policies reset constraints/iam.allowedPolicyMemberDomains --project=$DATA_PROJECT_ID
gcloud org-policies reset constraints/iam.allowedPolicyMemberDomains --project=$DOCAI_PROJECT_ID
```


### Provision Infrastructure and Set Access Rights
* The setup step takes care of the required access permissions and roles (user must have owner rights to the projects and be able to modify org policy and add IAM permissions).
* Service Account Key is generated in the current directory, which is used in the execution step. 
* Whenever setup is changed, env variables need to be updated and script below needs to be run again.
* 
```shell
./setup_docai_wh.sh
```

### Execution

For the processors other than OCR (since the schema will always be empty without any properties for the documents coming from the OCR parser), it is recommended to first follow these easy steps:
- [Generate document schema](#generate-draft-document-schema-using-docai-output-of-the-cde-processor)
- Manually inspect schema and verify types options
- [Upload document schema](#upload-document-schema-to-docai-wh)

Otherwise, schema will be generated on the fly without option to modify/edit with the best effort to guess the field types based on the DocAI output. Which is not always correct.

#### Generate Draft Document Schema 
- Using sample pdf document and the DocAI output, document schema is generated and saved locally with the document properties.
- The schema should be manually verified for the correctness of property types and then uploaded to document WH in the following step below.
- `display_name` of the generated document schema corresponds to the display name of the processor. However, this value could be overwritten.
- For the seamless batch upload step, it is easiest not to overwrite schema display name and leave it fall back to the default behaviour. 

> NB! `PATH_TO_PDF` must be inside the `DATA_PROJECT_ID`
> Processor `PROCESSOR_ID` must be inside the `DOCAI_PROJECT_ID`

```shell
export PROCESSOR_ID=<PROCESSOR_ID>
source SET
python generate_schema.py -f gs://<PATH-TO-PDF> [-sn schema_display_name]
```
Parameters:
```shell
-f -  Path to the GCS uri PDF for entity extraction used with PROCESSOR_ID, so that entities are used to generate the document schema.
-sn -  (optional) When specified, schema display name. Otherwise will use processor display name.
```

Example to generate schema for the fake invoice with assigned schema display_name:
```shell
export PROCESSOR_ID=<INVOICE_PROCESSOR_ID>
python generate_schema.py -f gs://${DATA_PROJECT_ID}-data/invoices/Invoice1.pdf -sn my_invoice
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

#### Upload Document Schema to DocAI WH
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

#### Batch Document Ingestion
- Out-of-the box when uploading documents, script will try to use schema with the display name same as the display name of the created user processor. If such schema does not exist, it will generate one.
- If user has provided either schema_id (`-s`) - it will use the existing schema_id when uploading the documents.
- If user has provided schema_name (`-sn`) option, script will first check if such schema exists, and if not, will generate one.


```shell
export PROCESSOR_ID=<PROCESSOR_ID>
source SET
python load_docs.py -d gs://<PATH-TO-DIR> [-n <NAME-OF-THE-ROOT-FOLDER>][-s schema_id] [-sn schema_display_name] [--flatten]  [-o] 
```
Parameters:
```shell
-d -  Path to the GCS storage folder, containing data with PDF documents to be loaded. All original structure of sub-folders will be preserved.
-n -  (optional) `Name` of the root folder inside DW to upload the documents/folders. When omitted, will the name of the folder/bucket being loaded from.
-s -  (optional) Existing `Schema_id` to be used when uploading the document. By default application relies on the processor.display_name and searches for schema with that name. 
-sn - (optional) Schema `display_name` either existing one to be used, or the new one to be created. By default application will rely on the `processor.display_name`. 
-o, --overwrite -  (optional) When set, will overwrite files if already exist. By default, will skip files based on the file path and file name.
--options - (optional) - When set (by default), will automatically fill in document properties using schema options.
--flatten - (optional) - When set, will flatten sub-directories. Otherwise (by default) preserves the original structure.
```

Example: Batch Upload with invoices (will generate/use existing schema with the processor display name):
```shell
export PROCESSOR_ID=<INVOICE_PROCESSOR_ID>
source SET
python load_docs.py -d gs://${DATA_PROJECT_ID}-data/invoices -n invoices
```

#### Delete Document Schema
A simple utility to delete schema either by id or by display_name:
```shell
export PROCESSOR_ID=<INVOICE_PROCESSOR_ID>
source SET
python delete_schema.py [-s <schema_id>] [-sn schema_name]
```
Example:
```shell
python delete_schema.py -s 661g7c10s8h7g -s 0d1jot5tqljsg -sn my_invoice
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

