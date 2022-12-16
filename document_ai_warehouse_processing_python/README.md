# Using Document AI Warehouse Python Client Library to run common operations on Document AI Warehouse

## Overview

This project demonstrates how to perform common actions on Document AI Warehouse through API.dw_processing.ipynb uses document_warehouse_utils.py for abstraction and readability. 
It is recommended to look at the code provided in the utils python files.

1. Create document & folder Schema. 
2. Create a folder using schema created in step #1.
3. Create a document using schema created in step #1 using inline raw document & set property values.
4. Create a document using schema created in step #1 using document stored in gcs & embed DocumentAI processor output alongwith.
5. Link document created in step #4 to the folder
6. Search document
7. Clean-up

## Prerequisites

1. Please ensure that you have a Document AI instance . You can follow this [quickstart](https://cloud.google.com/document-warehouse/docs/quickstart) to complete the setup.
2. Create a document AI [Invoice processor](https://cloud.google.com/document-ai/docs/processors-list#processor_invoice-processor) and update the DOCAI_PROCESSOR_ID variable below.
3. If you are using Vertex AI Workbench Managed jupyter lab, pls ensure to grant [roles/contentwarehouse.documentAdmin](https://cloud.google.com/document-warehouse/docs/manage-access-control) & [roles/documentai.apiUser](https://cloud.google.com/document-ai/docs/access-control/iam-roles). If you are using your own dev environment please ensure to grant the specified permissions to the identity.

## Setup

1. Install dependencies mentioned in requirements.txt
```commandline
pip install -r requirements.txt
```
2. Open dw_processing.ipynb and follow the step-by-step guide.
