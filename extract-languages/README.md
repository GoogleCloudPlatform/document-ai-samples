# Document AI PDF Splitter Sample

This project uses the Document AI API to split PDF documents.

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
    PROJECT_ID = "YOUR_PROJECT_ID"
    LOCATION = "us"  # Format is 'us' or 'eu'
    PROCESSOR_ID = "YOUR_PROCESSOR_ID"  # Create processor in Cloud Console
    ```

1. Run the sample: `python extract_languages.py`
1. Your output should look like this if using the sample document:

    ```console
    $ python3 extract-languages.py 
    Document processing complete.
        page_number language_code confidence
    0             1            en        98%
    1             1           und         2%
    2             2            th        62%
    3             2           und        20%
    4             2            en        15%
    5             2            bs         2%
    6             2            it         1%
    7             3            en        97%
    8             3            de         1%
    9             3           und         1%
    10            3            so         1%
    ```
