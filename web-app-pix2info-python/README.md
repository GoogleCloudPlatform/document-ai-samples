# From pixels to information with Document AI

After creating a new Google Cloud project, you can deploy the app:

- to Cloud Run or to App Engine,
- directly from your browser with [Cloud Shell](https://console.cloud.google.com/?cloudshell=true),
- using one command-line tool: `gcloud`.

## 🔧 Project setup

### Document AI API

```bash
# Enable Document AI
gcloud services enable documentai.googleapis.com
```

### Environment variables

```bash
# Your project
PROJECT_ID=$(gcloud config list --format "value(core.project)")

# Source on GitHub
GIT_USER="GoogleCloudPlatform"
GIT_REPO="document-ai-samples"
GITHUB_SOURCE="https://github.com/$GIT_USER/$GIT_REPO.git"

# Local source
PROJECT_SOURCE=~/$GIT_REPO/web-app-pix2info-python/src
```

### Source code

```bash
# Get the source code
cd ~
git clone $GITHUB_SOURCE

# Make sure you point to the right location
ls $PROJECT_SOURCE

# You should get the following:
# app.yaml  backend  Dockerfile  frontend  main.py  requirements.txt  samples
```

## 🚀 Deploying to Cloud Run

Enable the services:

- Artifact Registry stores your build artifacts.
- Cloud Build builds your app.
- Cloud Run deploys and serves your app.

```bash
gcloud services enable \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com
```

Deploy your app:

```bash
SERVICE="document-ai-demo"
# Choose your preferred deployment region
# See https://cloud.google.com/about/locations#region
CLOUD_RUN_REGION="europe-west6"
# Finetune the memory limit (animation generation consumes more memory)
# See https://cloud.google.com/run/docs/configuring/memory-limits
CLOUD_RUN_MEMORY="4Gi"

gcloud run deploy $SERVICE \
  --source $PROJECT_SOURCE \
  --region $CLOUD_RUN_REGION \
  --memory $CLOUD_RUN_MEMORY \
  --platform managed \
  --allow-unauthenticated \
  --quiet
```

Notes:

- For more details, see the `gcloud run deploy` [options](https://cloud.google.com/sdk/gcloud/reference/run/deploy).
- Deploying from source requires an Artifact Registry repository to store the build artifacts. By using the `--quiet` flag, you skip prompt confirmations and a default repository named `cloud-run-source-deploy` will automatically be created.

This gives an output like the following:

```text
…
Building using Buildpacks and deploying container to Cloud Run service [SERVICE] in project [PROJECT_ID] region [CLOUD_RUN_REGION]
OK Building and deploying new service... Done.
  OK Creating Container Repository...
  OK Uploading sources...
  OK Building Container... Logs are available at […].
  OK Creating Revision...
  OK Routing traffic...
  OK Setting IAM Policy...
Done.
Service [SERVICE] revision [SERVICE-REVISION] has been deployed and is serving 100 percent of traffic.
Service URL: https://SERVICE-PROJECTHASH-REGIONID.a.run.app
```

Before using the app for the first time, you need to create the Document AI processors.

Retrieve the app URL:

```bash
APP_URL=$( \
  gcloud run services describe $SERVICE \
    --region $CLOUD_RUN_REGION \
    --platform managed \
    --format "value(status.url)" \
)
```

Call this admin endpoint:

```bash
curl $APP_URL/admin/processors/setup
```

Check out the logs:

```bash
gcloud logging read \
  "resource.type=cloud_run_revision resource.labels.service_name=$SERVICE" \
  --project $PROJECT_ID \
  --format "value(textPayload)" \
  --freshness 5m
```

You should get logs like the following:

```text
.. Creating: eu / 6-ID_PROOFING_PROCESSOR
.. Creating: eu / 5-US_PASSPORT_PROCESSOR
…
.. Creating: us / 2-FORM_PARSER_PROCESSOR
.. Creating: us / 1-OCR_PROCESSOR
```

## 🚀 Deploying to App Engine

Alternatively, you can deploy the demo to App Engine.

```bash
# Enable Cloud Build
gcloud services enable cloudbuild.googleapis.com
```

Create the app:

```bash
# Choose your preferred deployment region
# See https://cloud.google.com/about/locations#region
APP_ENGINE_REGION="europe-west6"

gcloud app create --region $APP_ENGINE_REGION
```

This gives the following output:

```text
Creating App Engine application in project [PROJECT_ID] and region [APP_ENGINE_REGION]....done.
Success! The app is now created. Please use `gcloud app deploy` to deploy your first app.
```

Deploy your app:

```bash
gcloud app deploy $PROJECT_SOURCE/app.yaml --quiet
```

This gives an output like the following:

```text
…
File upload done.
Updating service [default]...done.
Setting traffic split for service [default]...done.
Deployed service [default] to [https://PROJECT_ID.REGIONID.r.appspot.com]
```

Before using the app for the first time, you need to create the Document AI processors.

Retrieve the app URL:

```bash
APP_URL=$(gcloud app describe --format "value(defaultHostname)")
```

Call this admin endpoint:

```bash
curl $APP_URL/admin/processors/setup
```

Check out the logs:

```bash
gcloud logging read \
  "resource.type=gae_app" \
  --project $PROJECT_ID \
  --format "value(textPayload)" \
  --freshness 5m
```

You should get logs like the following:

```text
.. Creating: eu / 6-ID_PROOFING_PROCESSOR
.. Creating: eu / 5-US_PASSPORT_PROCESSOR
…
.. Creating: us / 2-FORM_PARSER_PROCESSOR
.. Creating: us / 1-OCR_PROCESSOR
```

## 🎉 It's alive

Open the web app; your document analyzer app is live!

![demo animation](pics/22f_demo_camera.gif)
