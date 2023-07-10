# Document AI PDF Annotator Sample

This project uses the Document AI API to annotate PDF documents.

## Quick start

1. [Install Python](https://www.python.org/downloads/)
1. Install the prerequisites: `pip install -r requirements.txt`
1. Install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
1. Run `gcloud init` and create a new project
1. Enable the Document AI API: `gcloud services enable documentai.googleapis.com`
1. Setup application default authentication, run: `gcloud auth application-default login`
1. Clone this repo and run the sample: `python main.py -i invoice.pdf`. You
    should see the annotated document in the current directory named
    `invoice_annotated.pdf`.

## Setup

### Install dependencies

1. Install pyenv: https://github.com/pyenv/pyenv#installation
1. Use pyenv to install
    [the latest version of Python 3](https://www.python.org/downloads/) for
    example, to install Python version 3.10.1, run: `pyenv install 3.10.1`
1. Create a Python virtual environment with the installed version of Python 3,
    for example, to create a Python 3.10.1 virtual environment called
    `docai-annotator`, run: `pyenv virtualenv 3.10.1 docai-annotator`
1. Clone this repo and `cd` to the root of the repo
1. Configure pyenv to use the virtual python environment we created earlier when in this repo: `pyenv local docai-annotator`
1. Install the prerequisites: `pip install -r requirements.txt`

### Setup Google Cloud

1. Install the Cloud SDK: https://cloud.google.com/sdk/docs/install
1. Run `gcloud init`, to
    [create a new project](https://cloud.google.com/resource-manager/docs/creating-managing-projects#creating_a_project),
    and
    [link a billing to your project](https://cloud.google.com/sdk/gcloud/reference/billing)
1. Enable the Document AI API: `gcloud services enable
documentai.googleapis.com`
1. Setup application default authentication, run: `gcloud auth
application-default login`

## Testing

### Manual

1. Run the sample: `python main.py -i invoice.pdf`
1. Check to see the annotated version of the PDF created in the current directory with the name `invoice_annotated.pdf`.
