# Enterprise Knowledge Graph Search Demo

This demo illustrates how to search the public Cloud Knowledge Graph using the [Enterprise Knowledge Graph][1] API.

## Architecture

### Google Cloud Products Used

- [Enterprise Knowledge Graph][1]
- [Cloud Run][2]

[1]: https://cloud.google.com/enterprise-knowledge-graph/docs/overview
[2]: https://cloud.google.com/run

## Setup

### Dependencies

1. [Install Python](https://www.python.org/downloads/)
2. Install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
3. Install the prerequisites:
   - `pip install -r requirements.txt`
4. Run `gcloud init`, create a new project, and
   [enable billing](https://cloud.google.com/billing/docs/how-to/modify-project#enable_billing_for_a_project)
5. Enable the EKG API:
   - `gcloud services enable enterpriseknowledgegraph.googleapis.com`
6. Setup application default authentication, run:
   - `gcloud auth application-default login`

### Demo Deployment

1. Update the `consts.py` file with your own `PROJECT_ID` and `LOCATION`.

2. Deploy the Cloud Run app in your project.

   - `gcloud run deploy ekg-demo --source .`

3. Visit the deployed web page

---

> Copyright 2022 Google LLC
> Author: Holt Skinner
