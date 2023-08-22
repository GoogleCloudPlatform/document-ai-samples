# Copyright 2023 Google LLC
# SPDX-License-Identifier: Apache-2.0

terraform {
  # Require at least terraform 1.3.0 as it supports defaults for variables
  required_version = ">= 1.3.0, < 2.0.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "4.55.0"
    }
    http = {
      source  = "hashicorp/http"
      version = "3.3.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "2.3.0"
    }
  }
}

// configuration for impersonation of Google Cloud service account to run terraform

provider "google" {
  alias = "impersonation"
  scopes = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
  ]
}

provider "google" {
  project                     = var.project_id
  region                      = var.region
  access_token                = data.google_service_account_access_token.default.access_token
  impersonate_service_account = local.terraform_service_account
}


locals {
  terraform_service_account = var.terraform_service_account
}

data "google_service_account_access_token" "default" {
  provider               = google.impersonation
  target_service_account = local.terraform_service_account
  scopes                 = ["userinfo-email", "cloud-platform"]
  lifetime               = "1200s"
}

# Enable APIs

resource "google_project_service" "iam" {
  service = "iam.googleapis.com"
}

resource "google_project_service" "cloudresourcemanager" {
  service = "cloudresourcemanager.googleapis.com"
}

resource "google_project_service" "storage" {
  service = "storage.googleapis.com"
}

resource "google_project_service" "documentai" {
  service = "documentai.googleapis.com"
}

resource "google_project_service" "compute" {
  service = "compute.googleapis.com"
}

resource "google_project_service" "pubsub" {
  service = "pubsub.googleapis.com"
}

resource "google_project_service" "cloudfunctions" {
  service = "cloudfunctions.googleapis.com"
}

resource "google_project_service" "run" {
  service = "run.googleapis.com"
}

resource "google_project_service" "artifactregistry" {
  service = "artifactregistry.googleapis.com"
}

resource "google_project_service" "cloudbuild" {
  service = "cloudbuild.googleapis.com"
}

resource "google_project_service" "workflows" {
  service = "workflows.googleapis.com"
}

resource "google_project_service" "workflowexecutions" {
  service = "workflowexecutions.googleapis.com"
}

resource "google_project_service" "monitoring" {
  service = "monitoring.googleapis.com"
}

resource "google_project_service" "cloudscheduler" {
  service = "cloudscheduler.googleapis.com"
}

# Create service account for workflow

resource "google_service_account" "documentai" {
  account_id   = "documentai"
  display_name = "Document AI Service Account"
  depends_on   = [google_project_service.iam]
}

resource "google_project_iam_member" "documentai" {
  project = var.project_id
  for_each = toset([
    "roles/storage.admin",
    "roles/documentai.admin",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/logging.logWriter",
    "roles/pubsub.publisher",
    "roles/cloudfunctions.viewer",
    "roles/run.invoker",
    "roles/workflows.admin",
  ])
  role       = each.key
  member     = "serviceAccount:${google_service_account.documentai.email}"
  depends_on = [google_service_account.documentai, google_project_service.iam]
}

# Create storage resources

resource "google_storage_bucket" "source" {
  name                        = "${var.project_id}-source"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
  depends_on                  = [google_project_service.storage]
}

resource "google_storage_bucket" "uploads" {
  name                        = "${var.project_id}-uploads"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
  depends_on                  = [google_project_service.storage]
}

resource "google_storage_bucket" "processing" {
  name                        = "${var.project_id}-processing"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
  depends_on                  = [google_project_service.storage]
}

resource "google_storage_bucket" "results" {
  for_each                    = google_document_ai_processor.processor
  name                        = "${var.project_id}-results-${each.value.name}"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true

  dynamic "cors" {
    for_each = var.proxy_storage_requests ? [] : [1]
    content {
      origin          = ["https://${var.domain}"]
      method          = ["GET", "HEAD", "PUT", "POST", "DELETE"]
      response_header = ["*"]
      max_age_seconds = 3600
    }
  }

  depends_on = [google_project_service.storage]

  # as results may stay in the bucket longer, enable autoclass by default to reduce cost
  autoclass {
    enabled = true
  }
}

resource "google_storage_bucket" "failed" {
  name                        = "${var.project_id}-failed"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
  depends_on                  = [google_project_service.storage]

  # as results may stay in the bucket longer, enable autoclass by default to reduce cost
  autoclass {
    enabled = true
  }
}

resource "google_storage_bucket" "datasets" {
  name                        = "${var.project_id}-datasets"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
  depends_on                  = [google_project_service.storage]
}

# Document AI Processors

resource "google_document_ai_processor" "processor" {
  for_each     = var.processors
  location     = each.value.location
  display_name = each.value.display_name
  type         = each.value.type
  depends_on   = [google_project_service.documentai]
}


# Cloud Functions Configuration

# Compress source code
data "archive_file" "parse_results" {
  type        = "zip"
  source_dir  = "${path.module}/src/functions/parse-results"
  output_path = "${path.module}/files/parse-results.zip"
}

data "archive_file" "split_document" {
  type        = "zip"
  source_dir  = "${path.module}/src/functions/split-document"
  output_path = "${path.module}/files/split-document.zip"
}

# Add source code zip to bucket
resource "google_storage_bucket_object" "parse_results" {
  name   = "parse-results-${data.archive_file.parse_results.output_md5}.zip"
  bucket = google_storage_bucket.source.name
  source = data.archive_file.parse_results.output_path
}

resource "google_storage_bucket_object" "split_document" {
  name   = "split-document-${data.archive_file.split_document.output_md5}.zip"
  bucket = google_storage_bucket.source.name
  source = data.archive_file.split_document.output_path
}

# create functions
resource "google_cloudfunctions2_function" "parse_results" {
  name        = "parse-results"
  description = "Parse processor results"
  location    = var.region
  depends_on  = [google_project_service.cloudfunctions, google_project_service.run, google_project_service.artifactregistry]

  build_config {
    runtime     = "python310"
    entry_point = "parse_results" # Set the entry point 
    source {
      storage_source {
        bucket = google_storage_bucket.source.name
        object = google_storage_bucket_object.parse_results.name
      }
    }
  }

  service_config {
    available_memory      = "4Gi"
    timeout_seconds       = 3600
    ingress_settings      = "ALLOW_INTERNAL_AND_GCLB"
    max_instance_count    = 100
    service_account_email = google_service_account.documentai.email
  }
}

resource "google_cloudfunctions2_function" "split_document" {
  name        = "split-document"
  description = "Split documents"
  location    = var.region
  depends_on  = [google_project_service.cloudfunctions, google_project_service.run, google_project_service.artifactregistry]

  build_config {
    runtime     = "python310"
    entry_point = "split_document" # Set the entry point 
    source {
      storage_source {
        bucket = google_storage_bucket.source.name
        object = google_storage_bucket_object.split_document.name
      }
    }
  }

  service_config {
    available_memory      = "1Gi"
    timeout_seconds       = 600
    ingress_settings      = "ALLOW_INTERNAL_AND_GCLB"
    max_instance_count    = 100
    service_account_email = google_service_account.documentai.email
  }
}

# Deploy load_documents workflow
resource "google_workflows_workflow" "load_documents" {
  name            = "load_documents"
  description     = "Load documents from input bucket"
  region          = var.region
  service_account = google_service_account.documentai.email
  source_contents = file("${path.module}/src/workflows/load_documents.yaml")
  depends_on      = [google_project_service.workflows]
}

# Deploy batch_process_documents workflow
resource "google_workflows_workflow" "batch_process_documents" {
  name            = "batch_process_documents"
  description     = "Batch process documents"
  region          = var.region
  service_account = google_service_account.documentai.email
  source_contents = file("${path.module}/src/workflows/batch_process_documents.yaml")
  depends_on      = [google_project_service.workflows]
}

# Deploy process_result workflow
resource "google_workflows_workflow" "process_result" {
  name            = "process_result"
  description     = "Process document processing result"
  region          = var.region
  service_account = google_service_account.documentai.email
  source_contents = file("${path.module}/src/workflows/process_result.yaml")
  depends_on      = [google_project_service.workflows]
}

resource "google_cloud_scheduler_job" "trigger_load_documents_workflow" {
  name        = "trigger-load-documents-workflow"
  description = "trigger load_documents workflow"
  schedule    = "*/1 * * * *"

  retry_config {
    min_backoff_duration = "1s"
    max_retry_duration   = "30s"
    retry_count          = 3
  }

  http_target {
    http_method = "POST"
    uri         = "https://workflowexecutions.googleapis.com/v1/${google_workflows_workflow.load_documents.id}/executions"
    body = base64encode(
      jsonencode(
        {
          "argument" : jsonencode(
            {
              "buckets" : {
                "inputs" : google_storage_bucket.uploads.name,
                "processing" : google_storage_bucket.processing.name,
                "results" : "${var.project_id}-results-$${processorId}",
                "failed" : google_storage_bucket.failed.name,
              }
              "defaultProcessorName" : google_document_ai_processor.processor["default"].id
              "processors" : google_document_ai_processor.processor
              "workflows" : {
                "batchProcessDocuments" : google_workflows_workflow.batch_process_documents.id
                "processResult" : google_workflows_workflow.process_result.id
              }
              "config" : {
                "uploadBucket" : google_storage_bucket.uploads.name
              }
            }
          )
        }
      )
    )

    oauth_token {
      service_account_email = google_service_account.documentai.email
    }
  }
}

# monitoring and alerting

resource "google_monitoring_notification_channel" "email" {
  display_name = "E-mail notification channel"
  type         = "email"
  labels = {
    email_address = var.alert_notification_email
  }
}

resource "google_monitoring_alert_policy" "error_log_entry" {
  display_name = "Alert on error log entry"
  combiner     = "OR"
  conditions {
    display_name = "error log entry"
    condition_matched_log {
      filter = "severity = \"ERROR\""
    }
  }
  alert_strategy {
    notification_rate_limit {
      period = "300s"
    }
    auto_close = "604800s"
  }

  notification_channels = [google_monitoring_notification_channel.email.name]
}

resource "google_monitoring_alert_policy" "critical_log_entry" {
  display_name = "Alert on critical log entry"
  combiner     = "OR"
  conditions {
    display_name = "critical log entry"
    condition_matched_log {
      filter = "severity = \"CRITICAL\""
    }
  }
  alert_strategy {
    notification_rate_limit {
      period = "300s"
    }
    auto_close = "604800s"
  }

  notification_channels = [google_monitoring_notification_channel.email.name]
}

resource "google_monitoring_alert_policy" "quota_exceeded" {
  display_name = "Quota exceeded policy"
  combiner     = "OR"
  conditions {
    condition_threshold {
      aggregations {
        alignment_period     = "60s"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["metric.label.quota_metric"]
        per_series_aligner   = "ALIGN_COUNT_TRUE"
      }
      comparison = "COMPARISON_GT"
      duration   = "60s"
      filter     = "metric.type=\"serviceruntime.googleapis.com/quota/exceeded\" resource.type=\"consumer_quota\""
      trigger {
        count = 1
      }
    }
    display_name = "Quota exceeded error by label.quota_metric SUM"
  }

  notification_channels = [google_monitoring_notification_channel.email.name]
}
