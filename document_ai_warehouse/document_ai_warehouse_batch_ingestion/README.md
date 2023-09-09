# Guide to Batch Upload Documents into the Document AI Warehouse
<!-- TOC -->
* [Guide to Batch Upload Documents into the Document AI Warehouse](#guide-to-batch-upload-documents-into-the-document-ai-warehouse)
  * [Introduction](#introduction)
    * [Use Cases](#use-cases)
    * [Limitations](#limitations)
  * [Prerequisites](#prerequisites)
    * [Prepare Python Environment](#prepare-python-environment)
    * [Provision Document AI Warehouse](#provision-document-ai-warehouse)
  * [Quickstart Example](#quickstart-example)
  * [Detailed Instructions](#detailed-instructions)
    * [Setup](#setup)
      * [Set env Variables](#set-env-variables)
      * [Prepare GCS Bucket with Data](#prepare-gcs-bucket-with-data)
      * [Create Processor](#create-processor)
      * [Cross-Org Access - Only when required](#cross-org-access---only-when-required)
    * [Provision Infrastructure and Set Access Rights](#provision-infrastructure-and-set-access-rights)
    * [Execution](#execution)
      * [Generate Draft Document Schema](#generate-draft-document-schema)
      * [Upload Document Schema](#upload-document-schema)
      * [Batch Document Ingestion](#batch-document-ingestion)
      * [Delete Document Schema](#delete-document-schema)
  * [Troubleshooting](#troubleshooting)
<!-- TOC -->

## Introduction

This is a utility that allows a batch upload of Folders/Files stored in GCS bucket into the Document Warehouse using Processor to extract structured data.
Supported Features:

- Generation of the document schema based on the Document AI output.
- Filling in document properties using document schema and Document AI output.
- Batch upload using GCS uri as an input (can be in separate project different from the Document AI Warehouse project) while preserving the original folder structure.
- There is no limit on 15 pages per document, since asynchronous batch processing is used by the Document AI parser.
- When folder contains high amount of documents, it might take a while for a batch operation to complete.
  - When using Cloud Shell, this might time out on the session.
- Processors can be in a separate project different from the Document AI Warehouse project.
- Also, you are able to batch upload large amounts of documents with up to 200 pages, either using an OCR parser, or existing pre-trained or custom trained processors, along with the extracted properties.

### Use Cases

There are two main use Cases:

1. Batch upload of PDF documents containing Plain text (using OCR parser).
   - In this case the document schema will not contain any properties.
2. Batch upload of PDF forms containing special properties (using special parsers, such as pre-trained Invoice parser, or custom trained CDE Parser)
   - In this situation the document schema with properties has to be created based on the Document AI output.
   - While schema could be auto-magically created for you with the best effort and uploaded seamlessly in the upload operation, it is recommended to follow these steps for best accuracy:
     - Generate the document schema based on the Document AI processor output.
     - Inspect the generated schema and correct the types if necessary.
     - Upload the generated schema to the Document AI Warehouse.
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

### Provision Document AI Warehouse

- Create GCP Project wth a linked Billing Account.
- Enable [Document AI Warehouse API](https://pantheon.corp.google.com/apis/library/contentwarehouse.googleapis.com) in your Google Cloud project and click Next.

- Provision the Instance:
  - For now, use `Universal Access: No document level access control` for the ACL modes in Document AI Warehouse and click Provision, then Next.
  - Enable question and answering to help find documents using GenAI.
  - Skip Initialization - Create a document schema (Click Next)
  - Skip Service Account creation (Click Next)
  - Click Done

## Quickstart Example

For the Quick start demo you will be using single GCP project, Document AI Warehouse, Invoice parser and sample invoices.

1. Set env variable:

```shell
export PROJECT_ID="<insert here>"
```

2. Upload sample data:

```shell
gcloud storage buckets create gs://${PROJECT_ID}-data --project  $PROJECT_ID
gsutil -m cp -r sample_data/invoices/*  gs://${PROJECT_ID}-data/invoices/
```

3. Create Document AI Invoice parser: go to [GCP Document AI page](https://console.cloud.google.com/ai/document-ai/processors) and create [Invoice processor](https://cloud.google.com/document-ai/docs/processors-list#processor_invoice-processor).

Set processor ID:

```shell
export PROCESSOR_ID="<insert here>"
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
python main.py get_schema -f gs://${PROJECT_ID}-data/invoices/Invoice1.pdf -sn my_invoice
```

6. Open up the `schema_files/my_invoice.json` file to get familiar with the structure. For this example, schema generated is correct, but it is not always a case.

7. Upload generated schema:

```shell
python main.py upload_schema -f schema_files/my_invoice.json
```

8. Do the batch upload using the created and verified schema:

```shell
python main.py batch_ingest -d gs://${PROJECT_ID}-data/invoices -n invoices -sn my_invoice
```

9. Since for this demo schema is correctly generated out-of-the box, we could also have skipped steps 5-7.

- You can run following command to see how for the generated schema, processor name will be used
- Use --overwrite option, since files are already there, they have to be overwritten (using different schema):

```shell
python load_docs.py -d gs://${PROJECT_ID}-data/invoices -n invoices2  --overwrite
```

Below you will see more details explained and more options available.

## Detailed Instructions

### Setup

#### Set env Variables

In the simplest case, you will need to create only one GCP Project `PROJECT_ID` to host following resources:

- Document AI Warehouse Instance - `PROJECT_ID`
- Bucket with the PDF Documents - `PROJECT_ID`
- Document AI Processor(s) - `PROJECT_ID`

However, in some cases you want to keep everything in different projects or maybe you already have your production Pre-trained processor in one project and data ingested into another project. In that case, you will be working with three different projects:

- Document AI Warehouse Instance - `DOCAI_WH_PROJECT_ID`
- Bucket with the PDF Documents - `DATA_PROJECT_ID`
- Document AI Processor(s) - `DOCAI_PROJECT_ID`

based on the situation, set the env variables accordingly:

```shell
export PROJECT_ID="<insert here>"     # This is the default ID for all Projects if you want to have all in the same project

# Otherwise, manually setup the following:
export DOCAI_WH_PROJECT_ID="<insert here>"  # Project ID of the GCP Project in which Document AI Warehouse has been provisioned
export DATA_PROJECT_ID= "<insert here>"     # Project ID with GCS Data to be Loaded
export DOCAI_PROJECT_ID="<insert here>"     # Project ID of the GCP Project with Document AI Processor used for document parsing
```

#### Prepare GCS Bucket with Data

- You can either use same single project (`PROJECT_ID`), or a different GCP project (`DATA_PROJECT_ID`) wth a linked Billing Account.
- Upload pdf forms that you want to ingest into DocumentAI warehouse into the GCS bucket.
  - Currently, only PDF documents are supported.
- GCS bucket can have hierarchical structure, which will be preserved when loading into the Document AI Warehouse.

#### Create Processor

- You can either use same single project (`PROJECT_ID`), or a different GCP project (`DOCAI_PROJECT_ID`) wth a linked Billing Account.
- It could be an existing Project with the trained processor(s) or,
- Create a processor to parse the documents, such as an OCR processor (to extract text data) or CDE processor (trained for the custom forms) or use one of the pre-trained processors, such as Invoice parser.
- Note down Processor ID.

#### Cross-Org Access - Only when required

In case if your projects are under different organizations, you need to make sure that [domain restriction domain](https://cloud.google.com/resource-manager/docs/organization-policy/restricting-domains) is disabled,
by [setting the organization policy](https://cloud.google.com/resource-manager/docs/organization-policy/restricting-domains#setting_the_organization_policy).

Simplest but most permissive solution is to set policy constraint `constraints/iam.allowedPolicyMemberDomain` to `Allowed All`:

```shell
gcloud org-policies reset constraints/iam.allowedPolicyMemberDomains --project=$DOCAI_WH_PROJECT_ID
gcloud org-policies reset constraints/iam.allowedPolicyMemberDomains --project=$DATA_PROJECT_ID
gcloud org-policies reset constraints/iam.allowedPolicyMemberDomains --project=$DOCAI_PROJECT_ID
```

### Provision Infrastructure and Set Access Rights

- The setup step takes care of the required access permissions and roles (user must have owner rights to the projects and be able to modify org policy and add IAM permissions).
- Service Account Key is generated in the current directory, which is used in the execution step.
- Whenever setup is changed, env variables need to be updated and script below needs to be run again.

```shell
./setup_docai_wh.sh
```

### Execution

For the processors other than OCR (since the schema will always be empty without any properties for the documents coming from the OCR parser), it is recommended to first follow these easy steps:

- [Generate Draft Document Schema](#generate-draft-document-schema)
- Manually inspect schema and verify types options
- [Upload Document Schema](#upload-document-schema)

Otherwise, schema will be generated on the fly without option to modify/edit with the best effort to guess the field types based on the Document AI output. Which is not always correct.

#### Generate Draft Document Schema

- Using sample pdf document and the Document AI output, document schema is generated and saved locally with the document properties.
- The schema should be manually verified for the correctness of property types and then uploaded to document Warehouse in the following step below.
- `display_name` of the generated document schema corresponds to the display name of the processor. However, this value could be overwritten.
- For the seamless batch upload step, it is easiest not to overwrite schema display name and leave it fall back to the default behaviour.
- You can either set environment variable PROCESSOR_ID or provide Processor ID as an input parameter (`-p PROCESSOR_ID`):
> NB! `PATH_TO_PDF` must be inside the `DATA_PROJECT_ID`
> Processor `PROCESSOR_ID` must be inside the `DOCAI_PROJECT_ID`

```shell
source SET
python main.py get_schema -f gs://<PATH-TO-PDF> [-sn schema_display_name] -p <PROCESSOR_ID>
```

Parameters:

```shell
-f  -  Path to the GCS uri PDF for entity extraction used with PROCESSOR_ID, so that entities are used to generate the document schema.
-sn -  (optional) When specified, schema display name. Otherwise will use processor display name.
-p  - processor ID sued by the Document AI.
```

Example to generate schema for the fake invoice with assigned schema display_name:

```shell
python main.py get_schema -f gs://${DATA_PROJECT_ID}-data/invoices/Invoice1.pdf -sn my_invoice -p <INVOICE_PROCESSOR_ID>
```

Sample output:

```text
batch_extraction - Calling Processor API for 1 document(s) batch_extraction - Calling Document AI API for 1 document(s)  using inv processor type=INVOICE_PROCESSOR, path=projects/978098347395/locations/us/processors/18849599a3ece785
batch_extraction - Waiting for operation projects/978098347395/locations/us/operations/6041130884555864540 to complete...
batch_extraction - Elapsed time for operation 22 seconds
batch_extraction - Handling Document AI results for gs://...-data/invoices/Invoice1.pdf using process output gs://...-docai-output/6041130884555864540/0
Generated /Users/.../document-ai-samples/document_ai_warehouse/batch-ingestion-docai-wh/schema_files/my_invoice.json with document schema for gs://...-data/invoices/Invoice1.pdf
```

Now, open and verify `schema_files/my_invoice.json`.

#### Upload Document Schema

After you have generated and verified document schema, it is time to upload it to the Document AI Warehouse.
To avoid confusions, if there is already existing schema with same display_name, operation will be skipped (unless -o option is used).
Please note, that overwriting with `-o` option is not possible, if there are already existing documents using that schema. You will need to first remove all the existing documents using that schema.

```shell
source SET
python main.py upload_schema -f schema_files/<schema_name>.json
```

Parameters:

```shell
-f -  Path to JSON file stored locally with the document schema.
-o -  (optional) When set, will overwrite existing schema with the same display name, otherwise (default) will skip upload action. However if there are already files using that schema, the application would not be able to overwrite schema and will skip.
```

Example:

```shell
python main.py upload_schema -f schema_files/my_invoice.json
```

Sample output:

```text
create_document_schema - Created document schema with display_name = my_invoice and schema_id = 0tv9nva44dnf0
```

#### Batch Document Ingestion

- Out-of-the box when uploading documents, script will try to use schema with the display name same as the display name of the created user processor. If such schema does not exist, it will generate one.
- If user has provided either schema_id (`-s`) - it will use the existing schema_id when uploading the documents.
- If user has provided schema_name (`-sn`) option, script will first check if such schema exists, and if not, will generate one.
- You can either set environment variable PROCESSOR_ID or provide Processor ID as an input parameter (`-p PROCESSOR_ID`):

```shell
source SET
python main.py batch_ingest -d gs://<PATH-TO-DIR> [-p <PROCESSOR_ID>] [-n <NAME-OF-THE-ROOT-FOLDER>] [-s schema_id] [-sn schema_display_name] [--flatten] [-o]
```

Parameters:

```shell
-d  -  Path to the GCS storage folder, containing data with PDF documents to be loaded. All original structure of sub-folders will be preserved.
-p  - (optional) processor ID used by the Document AI. When not provided will check for env variable PROCESSOR_ID. 
-n  -  (optional) `Name` of the root folder inside DW to upload the documents/folders. When omitted, will the name of the folder/bucket being loaded from.
-s  -  (optional) Existing `Schema_id` to be used when uploading the document. By default application relies on the processor.display_name and searches for schema with that name.
-sn - (optional) Schema `display_name` either existing one to be used, or the new one to be created. By default application will rely on the `processor.display_name`.
-o, --overwrite -  (optional) When set, will overwrite files if already exist. By default, will skip files based on the file path and file name.
--options - (optional) - When set (by default), will automatically fill in document properties using schema options.
--flatten - (optional) - When set, will flatten sub-directories. Otherwise (by default) preserves the original structure.
```

Example: Batch Upload with invoices (will generate/use existing schema with the processor display name):

```shell
export PROCESSOR_ID=<INVOICE_PROCESSOR_ID>
source SET
python main.py batch_ingest -d gs://${DATA_PROJECT_ID}-data/invoices -n invoices
```

#### Delete Document Schema

A simple utility to delete schema either by id or by display_name:

```shell
export PROCESSOR_ID=<INVOICE_PROCESSOR_ID>
source SET
python main.py delete_schema [-ss <schema_id>] [-sns schema_name]
```

Example:

```shell
python main.py delete_schema -ss 661g7c10s8h7g -ss 0d1jot5tqljsg -sns my_invoice1 -sns my_invoice2
```

## Troubleshooting

### Error 403 `IAM_PERMISSION_DENIED` Permission Denied

`403 Permission 'contentwarehouse.documentSchemas.list' denied on resource '//contentwarehouse.googleapis.com/projects/35407211402/locations/us' (or it may not exist). [reason: "IAM_PERMISSION_DENIED"`

**Solution**: I have noticed it takes up to ten minutes for the roles to be properly propagated to the service account.

- Make sure all rights are properly assigned:

```shell
gcloud projects get-iam-policy $DOCAI_WH_PROJECT_ID --flatten="bindings[].members" --format='table(bindings.role)' --filter="bindings.members:${SA_EMAIL}"
```

Expected Output:

```text
ROLE
ROLE: roles/contentwarehouse.admin
ROLE: roles/contentwarehouse.documentAdmin
ROLE: roles/documentai.apiUser
ROLE: roles/logging.logWriter
ROLE: roles/documentai.viewer
```