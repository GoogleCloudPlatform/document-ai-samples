# Document AI PDF Splitter Sample

This project uses the Document AI API to split PDF documents.

## Quick start

1.  [Install Python](https://www.python.org/downloads/)
1.  Install the prerequisites: `pip install -r requirements.txt`
1.  Install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
1.  Run `gcloud init`, create a new project, and
    [enable billing](https://cloud.google.com/billing/docs/how-to/modify-project#enable_billing_for_a_project)
1.  Enable the Document AI API: `gcloud services enable
    documentai.googleapis.com`
1.  Setup application default authentication, run: `gcloud auth
    application-default login`
1.  Run the sample: `python main.py -i multi_document.pdf`. You
    should see the split up sub-documents in your current directory with file
    names like `subdoc_X_of_8_multi_document.pdf`.

## Setup

### Install dependencies

1.  Install pyenv: https://github.com/pyenv/pyenv#installation
1.  Use pyenv to install
    [the latest version of Python 3](https://www.python.org/downloads/) for
    example, to install Python version 3.10.1, run: `pyenv install 3.10.1`
1.  Create a Python virtual environment with the installed version of Python 3,
    for example, to create a Python 3.10.1 virtual environment called
    `docai-splitter`, run: `pyenv virtualenv 3.10.1 docai-splitter`
1.  Clone this repo and `cd` to the root of the repo
1.  Configure pyenv to use the virtual python environment we created earlier
    when in this repo: `pyenv local docai-splitter`
1.  Install the prerequisites: `pip install -r requirements.txt`

### Setup Google Cloud

1.  Install the Cloud SDK: https://cloud.google.com/sdk/docs/install
1.  Run `gcloud init`, to
    [create a new project](https://cloud.google.com/resource-manager/docs/creating-managing-projects#creating_a_project),
    and
    [link a billing to your project](https://cloud.google.com/sdk/gcloud/reference/billing)
1.  Enable the Document AI API: `gcloud services enable
    documentai.googleapis.com`
1.  Setup application default authentication, run: `gcloud auth
    application-default login`

### Running the sample

1.  Run the sample: `python main.py -i multi_document.pdf`
1.  Check to see that the PDFs created in the current directory are
    sub-documents of `multi-document.pdf`.

## Testing

### Linting

1.  Install dependencies:

    ```
    pip install -U pylint
    ```

1.  Run the linter:

    ```
    pylint *.py
    ```

### Unit tests

1.  Run the unit tests: `python main_test.py`

### Manual

1.  Run the sample: `python main.py -i multi_document.pdf`
1.  Check to see that the PDFs created in the current directory are
    sub-documents of `multi-document.pdf`.
