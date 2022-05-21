# Sorting post-HITL Documents by language

This project uses the languages detected by Document AI (post-HITL) to sort the `Document.json` files into separate Cloud Storage buckets.
The document files are sorted by the most frequent language in the document, if there are multiple detected.

## Running the sample

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
