# Document AI Specialized Pipeline

This example illustrates how to create an automated pipeline using a Specialized Splitter-Classifier and multiple Specialized Parsers.

Includes examples for Online Processing with a small amount of documents, and Batch Processing for large quantities of documents.

## Setup steps

1. Clone Repo

    `git clone <https://github.com/GoogleCloudPlatform/document-ai-samples.git>`

1. Switch to Branch

    `git checkout processor-map`

1. Enter Directory

    `cd document-ai-samples/specialized-pipeline`

1. Install Dependencies

    `pip3 install -r requirements.txt`

1. Add Project Information in [`consts.py`](consts.py)

    ```py
    PROJECT_ID = "PROJECT_ID"
    LOCATION = "us"
    PROCESSOR_ID = "PROCESSOR_ID"
    ```

1. Add Document PDFs to the Cloud Storage bucket named `{PROJECT_ID}-input-invoices`

1. Run the Code

    `python3 pipeline.py`
