# Document AI Workbench Workflows

## Overview

- This solution is deployed using Terraform which is available in the Google Cloud Shell, which is also the preferred way to deploy the solution for testing and demo purposes
- While some Terraform knowledge is useful, it is not necessary
- This solution requires a dedicated GCP project

## Infrastructure Setup

1. Use the Open in Cloud Shell button above to clone the git repository (recommended) or manually clone [the repository](https://source.developers.google.com/p/ffeldhaus-permanent/r/docai-demo)
2. Setup a Service Account for Terraform and make sure your user can impersonate the service account
3. Create a dedicated GCP Project for this solution
4. In the newly created GCP Project in IAM grant `roles/owner` to the Terraform Service Account

## Terraform Configuration

Create a Terraform variable file and define all necessary variables. This will setup the solution specific to your needs.

1. Copy the `terraform.tfvars` file from the `examples` folder to the base folder of your solution e.g. using `cp examples/terraform.tfvars .`
2. Edit the `terraform.tfvars` file and adapt to your needs. Check the `variables.tf` file for the definition and further information on available variables

## Apply Terraform Configuration

1. Initialize Terraform with `terraform init`
2. Apply Terraform Configuration with `terraform apply`

## Usage

The solution expects that files are uploaded to the upload GCS Bucket.

Once a document is uploaded, a Google Cloud Workflow will be triggered to process the document.

## Troubleshooting

### Terraform

#### Slow

If terraform takes a long time, you can try speeding it up by adding [the parameter `--parallelism` to `terraform apply` (default is 10)](https://developer.hashicorp.com/terraform/cli/commands/apply#parallelism-n) e.g. 

```
terraform apply --parallelism=20
```

#### Problems during terraform init with GCS backend bucket

If you use a GCS backend bucket for terraform and get an error during `terraform init` it may be due to the Application Default Credentials not being set to the right project. Replace <your-project> and run:

```
gcloud auth application-default login --project <your-project>
```