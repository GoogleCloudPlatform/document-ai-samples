# Document Search and Synthesis - Generative AI Use Case

This demo illustrates how to search through a corpus of unstructrued contract documents using [Generative AI App Builder: Enterprise Search][1].

## Architecture

### Google Cloud Products Used

- [Generative AI App Builder: Enterprise Search][1]
- [Cloud Run][2]

[1]: https://cloud.google.com/generative-ai-app-builder/docs/overview
[2]: https://cloud.google.com/run

## Setup

- Follow steps in [Get started with Enterprise Search](https://cloud.google.com/generative-ai-app-builder/docs/try-enterprise-search) for Unstructured Data
- Use sample data `gs://cloud-samples-data/gen-app-builder/search/CUAD_v1`
  - Data Source: [Contract Understanding Atticus Dataset (CUAD)](https://www.atticusprojectai.org/cuad)
- Copy HTML code from `Integration > Widget` tab in Console.
- Deploy using Cloud Run

### Dependencies

1. [Install Python](https://www.python.org/downloads/)
2. Install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
3. Install the prerequisites:
   - `pip install -r requirements.txt`
4. Run `gcloud init`, create a new project, and
    [enable billing](https://cloud.google.com/billing/docs/how-to/modify-project#enable_billing_for_a_project)
5. Enable the Generative AI App Builder API:
   - `gcloud services enable discoveryengine.googleapis.com`
6. Setup application default authentication, run:
   - `gcloud auth application-default login`

### Demo Deployment

1. Deploy the Cloud Run app in your project.
   - `gcloud run deploy genappbuilder-demo --source .`

1. Visit the deployed web page
   - Example: https://genappbuilder-demo-lnppzg3rxa-uc.a.run.app

-----

> Copyright 2022 Google LLC
> Author: Holt Skinner
