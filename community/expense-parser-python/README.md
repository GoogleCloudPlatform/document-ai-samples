# Expense Parser Demo (Python)

## Description

This repository constructs an end-to-end pipeline on GCP to process expenses (ie. receipts) with the Document AI API. This repository serves as a sample code to build your own demo but is not tested for production.

## Visualizing the workflow

![GCP Workflow](https://user-images.githubusercontent.com/47513414/150703075-8f608859-436e-4c22-8dc9-f71121705f3a.png)

## GCP Services used in the Demo

- [Google Cloud Procurement Document AI](https://cloud.google.com/solutions/procurement-doc-ai)
- [Google Cloud Storage](https://cloud.google.com/storage)
- [Google Cloud Functions](https://cloud.google.com/functions)
- [BigQuery](https://cloud.google.com/bigquery)

## Steps to re-create this demo in your own GCP environment

1. Create a Google Cloud Platform Project

2. Enable the **Cloud Document AI API**, **Cloud Functions API** and **Cloud Build API** in the project you created in step #1.

3. If you do not have access to the parser, request access via [this link](https://docs.google.com/forms/d/e/1FAIpQLSc_6s8jsHLZWWE0aSX0bdmk24XDoPiE_oq5enDApLcp1VKJ-Q/viewform?gxids=7826). Here is a [link](https://cloud.google.com/document-ai/docs/processors-list#processor_expense-parser) to the official Expense Parser documentation.

4. Create a service account that will later be used by Cloud Functions

   1. Navigate to **IAM & Admin** -> **Service Accounts**
   2. Click on **Create a service account**
   3. In the **Service account name** section, type in `process-receipt-example` or a name of your choice
   4. Click **Create and continue**
   5. Grant this service account the following roles:
      - Storage Admin
      - BigQuery Admin
      - Document AI API User
   6. Click **Done** and you should see this service account in the IAM main page
      ![Service account on IAM main page](https://user-images.githubusercontent.com/47513414/150855283-cd78ba61-cada-4e2b-a35c-68accbde5eff.png)

5. Create your Doc AI processor

   - At this point, you should have your request in Step 3 approved and have access to expense parser
   - Navigate to **console** -> **Document AI** -> **processors**
   - Click **Create processor** and choose **expense parser**
   - Name your processor and click **Create**
   - Take note of your processor's region (eg. us) and processor ID

6. Activate your Cloud Shell and clone this GitHub repository in your Command shell using the command:

```shell
gh repo clone GoogleCloudPlatform/document-ai-samples
```

Note: If you are using your local terminal, please follow this [link](https://cloud.google.com/sdk/docs/install) to install and initiate Google Cloud CLI before this step.

7. Execute Bash shell scripts in your Cloud Shell terminal to create cloud resources (i.e Google Cloud Storage Buckets, Pub/Sub topics, Cloud Functions, BigQuery dataset and table)

   1. Change directory to the scripts folder

      ```shell
      cd community/expense-parser-python
      ```

   2. Update the following values in .env.local:

      - PROJECT_ID should match your current project's ID
      - BUCKET_LOCATION is where you want the raw receipts to be stored
      - CLOUD_FUNCTION_LOCATION is where your code executes
      - CLOUD_FUNCTION_SERVICE_ACCOUNT should be the same name you created in Step 4

      ```shell
      vim .env.local
      ```

   3. Make your .sh files executable

      ```shell
      chmod +x set-up-pipeline.sh
      ```

   4. Change directory to the cloud functions folder

      ```shell
      cd cloud-functions
      ```

   5. Update the following values in .env.yaml (from your note in Step 5):

      - PARSER_LOCATION
      - PROCESSOR_ID

      ```shell
      vim .env.yaml
      ```

   6. Go back to the original folder and execute your .sh files to create cloud resources
      ```shell
      cd ..
      ./set-up-pipeline.sh
      ```

8. Testing/Validating the demo

   1. Upload a sample receipt in the input bucket (<project_id>-input-receipts)
   2. At the end of the processing, you should expect your BigQuery tables to be populated with extracted entities (eg. total_amount, supplier_name, etc.). Note that each row is an extracted entity instead of a document.
   3. With the structured data in BigQuery, we can now design downstream analytical tools to gain actionable insights as well as detect errors/frauds.

## Disclaimer

This community sample is not officially maintained by Google.
