# Document AI DSPA Invoice Parser Demo

This example illustrates how to create an automated pipeline using a Specialized Splitter-Classifier and multiple Specialized Parsers

## Setup steps

1. Clone Repo

    `git clone https://github.com/GoogleCloudPlatform/document-ai-samples.git`

1. Switch to Branch

    `git checkout processor-map`

1. Enter Directory

    `cd document-ai-samples/dspa`

1. Add Project Configuration Information to [`consts.py`](consts.py) and [`setup/setup.sh`](setup/setup.sh)

    - Project ID(s)
    - Document AI Processors
    - Cloud Storage Buckets
    - BigQuery Datasets/Tables

1. Create Resources & Deploy Application

    `bash setup/setup.sh`

1. Grant App Engine Service Account IAM Permissions

    - Document AI Viewer
    - BigQuery Data Editor
    - Storage Admin (Project and Bucket Level)

1. For manual running of the pipeline, Add Document PDFs to the Cloud Storage Bucket and directory (`GCS_INPUT_BUCKET` `GCS_INPUT_PREFIX`) specified in `consts.py` and run the function `bulk_pipeline()` in [`pipeline.py`](pipeline.py)

1. In the deployed Web Application, upload files on the homepage and the processing pipeline will be initiated by a cron job at endpoint `/process_documents`
