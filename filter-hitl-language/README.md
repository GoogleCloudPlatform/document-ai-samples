# Filtering Documents post-HITL by language

This project uses the languages detected by Document AI (post-HITL) to sort the `Document.json` files into separate Cloud Storage buckets

## Setup


<!-- ### Setup Google Cloud

1. Install the Cloud SDK: <https://cloud.google.com/sdk/docs/install>
2. Run `gcloud init`, to
    [create a new project](https://cloud.google.com/resource-manager/docs/creating-managing-projects#creating_a_project),
    and
    [link a billing to your project](https://cloud.google.com/sdk/gcloud/reference/billing)
3. Enable the Document AI API:
    `gcloud services enable documentai.googleapis.com`
4. Setup application default authentication, run:
    `gcloud auth application-default login` -->

### Running the sample

1. Install the prerequisites: `pip install -r requirements.txt`

1. Update the following values with information from your project

    ```python
    PROJECT_ID = "YOUR PROJECT ID"

    # Output Files from Human-in-the-loop
    GCS_HITL_BUCKET = "input-bucket"
    GCS_HITL_PREFIX = "input-directory"

    # Output Bucket names will be in the format of GCS_OUTPUT_BUCKET_PREFIX + language
    GCS_OUTPUT_BUCKET_PREFIX = "output-bucket-"
    ```

1. Run the sample: `python main.py`
