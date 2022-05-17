# Document AI - Identity Form Autofiller

After creating a new Google Cloud project, you can deploy the app:

- to Cloud Run or App Engine,
- directly from your browser with [Cloud Shell](https://console.cloud.google.com/?cloudshell=true),
- using one command-line tool: `gcloud`.

## 🔧 Project setup

### Identity processors

This demo has an admin endpoint (`/admin/processors/check`) to automatically create processors:

1. Generally available identity processors will be created automatically.
2. Processors in Preview or Experimental are not allowed by default. To request access to these processors, please fill out the [Access Request Form](https://docs.google.com/forms/d/e/1FAIpQLSc_6s8jsHLZWWE0aSX0bdmk24XDoPiE_oq5enDApLcp1VKJ-Q/viewform).

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
PROJECT_SOURCE=~/$GIT_REPO/community/identity-form-autofiller-python/src

# Choose your preferred deployment region
# See https://cloud.google.com/about/locations#region
APP_ENGINE_REGION="europe-west6"
CLOUD_RUN_REGION="europe-west6"
```

### Source code

```bash
# Get the source code
cd ~
git clone $GITHUB_SOURCE

# Make sure you point to the right location
ls $PROJECT_SOURCE

# You should get the following:
# app.yaml  docai_procs.py  docai.py  main.py  Procfile  requirements.txt  samples  static
```

## 🚀 Deploying to Cloud Run

Enable the APIs:

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
SERVICE="identity-form-autofiller"

gcloud run deploy $SERVICE \
  --source $PROJECT_SOURCE \
  --region $CLOUD_RUN_REGION \
  --platform managed \
  --allow-unauthenticated \
  --quiet
```

Notes:
- For more details, see the `gcloud run deploy` [options](https://cloud.google.com/sdk/gcloud/reference/run/deploy)
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

Before using the app for the first time, you need to create Document AI identity processors.

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
curl $APP_URL/admin/processors/check
```

Check out the logs:

```bash
gcloud logging read \
  "resource.type=cloud_run_revision resource.labels.service_name=$SERVICE" \
  --project=$PROJECT_ID \
  --format="value(textPayload)" \
  --freshness=5m
```

You should get logs like the following:

```text
.. Creating: us / US_DRIVER_LICENSE_PROCESSOR
.. Creating: us / US_PASSPORT_PROCESSOR
…
.. Creating: eu / US_DRIVER_LICENSE_PROCESSOR
.. Creating: eu / US_PASSPORT_PROCESSOR
…
```

Note: You can ignore 40X errors with reason "PROCESSOR_NOT_ALLOWED" or "PROCESSOR_TYPE_NOT_FOUND". They will occur for processors not enabled for your project (see the Access Request Form earlier).

## 🚀 Deploying to App Engine

Alternatively, you can deploy the demo to App Engine.

Enable the Cloud Build API:

```bash
gcloud services enable cloudbuild.googleapis.com
```

Create the app:

```bash
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

Before using the app for the first time, you need to create Document AI identity processors.

Retrieve the app URL:

```bash
APP_URL=$(gcloud app describe --format "value(defaultHostname)")
```

Call this admin endpoint:

```bash
curl $APP_URL/admin/processors/check
```

Check out the logs:

```bash
gcloud app logs read --limit=25
```

You should get logs like the following:

```text
.. Creating: us / US_DRIVER_LICENSE_PROCESSOR
.. Creating: us / US_PASSPORT_PROCESSOR
…
.. Creating: eu / US_DRIVER_LICENSE_PROCESSOR
.. Creating: eu / US_PASSPORT_PROCESSOR
…
```

Note: You can ignore 40X errors with reason "PROCESSOR_NOT_ALLOWED" or "PROCESSOR_TYPE_NOT_FOUND". They will occur for processors not enabled for your project (see the Access Request Form earlier).

## 🎉 It's alive

Open the web app; your identity form autofiller is live!

![demo animation](pics/G_docai-identity-processor-demo-3.gif)

## Disclaimer

This community sample is not officially maintained by Google.
