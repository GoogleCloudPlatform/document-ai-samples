# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

terraform {
  # 1.7+ is needed for `import` blocks with for_each (Day 0 adoption of existing processors).
  required_version = ">= 1.7.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0.0"
    }
  }
}

provider "google" {
  project = var.destination_project_id
}

data "google_project" "destination" {
  project_id = var.destination_project_id
}

locals {
  manifest_files = var.manifests_dir != "" ? fileset("${path.module}/${var.manifests_dir}", "*.yaml") : toset([])

  manifest_processors = {
    for f in local.manifest_files :
    trimsuffix(f, ".yaml") => yamldecode(file("${path.module}/${var.manifests_dir}/${f}"))
  }

  # When manifests_dir is set, iterate over all *.yaml manifests in that folder.
  # Otherwise fall back to the single processor configured in terraform.tfvars.
  processors = length(local.manifest_processors) > 0 ? {
    for k, m in local.manifest_processors : k => {
      source_project_id          = try(m.source_project_id, var.source_project_id)
      source_processor_id        = m.source_processor
      destination_location       = try(m.location, var.destination_location)
      destination_processor_id   = try(m.destination_processor, "")
      destination_display_name   = try(m.display_name, "")
      versions_mode              = try(m.versions_mode, "default")
      specific_version_id        = try(m.source_version_id, "")
      deploy_version             = try(m.deploy, var.deploy_version)
      set_default_version        = try(m.set_default, var.set_default_version)
      copy_dataset               = try(m.copy_dataset, var.copy_dataset)
      allow_dataset_purge        = try(m.allow_dataset_purge, var.allow_dataset_purge)
      destination_dataset_bucket = try(m.destination_dataset_bucket, var.destination_dataset_bucket)
      schema_file                = try(m.schema_file, "")
      export_schema_path         = try(m.export_schema_path, "")
      processor_type             = try(m.processor_type, "CUSTOM_EXTRACTION_PROCESSOR")
      existing_processor_id      = try(m.existing_processor_id, "")
    }
    } : (
    var.source_processor_id != "" ? {
      default = {
        source_project_id          = var.source_project_id
        source_processor_id        = var.source_processor_id
        destination_location       = var.destination_location
        destination_processor_id   = var.destination_processor_id
        destination_display_name   = var.destination_display_name
        versions_mode              = var.versions_mode
        specific_version_id        = var.specific_version_id
        deploy_version             = var.deploy_version
        set_default_version        = var.set_default_version
        copy_dataset               = var.copy_dataset
        allow_dataset_purge        = var.allow_dataset_purge
        destination_dataset_bucket = var.destination_dataset_bucket
        schema_file                = var.schema_file
        export_schema_path         = var.export_schema_path
        processor_type             = "CUSTOM_EXTRACTION_PROCESSOR"
        existing_processor_id      = ""
      }
    } : {}
  )

  # Processors that Terraform creates natively (manifest mode only). The single-processor
  # fallback keeps today's behaviour, where the script creates the processor itself.
  native_processors = var.manage_processors_natively ? local.manifest_processors : {}

  is_cross_project = var.source_project_id != "" && var.source_project_id != var.destination_project_id
  any_copy_dataset = var.copy_dataset || anytrue([for p in values(local.processors) : p.copy_dataset])
  dest_docai_sa    = "serviceAccount:service-${data.google_project.destination.number}@gcp-sa-prod-dai-core.iam.gserviceaccount.com"
}

# 1. Authorize destination Document AI SA to read/export from source project (only needed if cross-project)
resource "google_project_iam_member" "source_docai_editor" {
  count   = local.is_cross_project ? 1 : 0
  project = var.source_project_id
  role    = "roles/documentai.editor"
  member  = local.dest_docai_sa
}

# 2. Authorize destination SA to read source dataset GCS bucket (if dataset copy is enabled and cross-project)
resource "google_project_iam_member" "source_storage_viewer" {
  count   = local.any_copy_dataset && local.is_cross_project ? 1 : 0
  project = var.source_project_id
  role    = "roles/storage.objectViewer"
  member  = local.dest_docai_sa
}

# 3. Create destination dataset & snapshot bucket with Object Versioning enabled so backups cannot be lost
resource "google_storage_bucket" "dest_dataset" {
  count                       = local.any_copy_dataset && var.destination_dataset_bucket != "" ? 1 : 0
  name                        = var.destination_dataset_bucket
  project                     = var.destination_project_id
  location                    = var.destination_location
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = true
  }
}

# 4. Destination processors as native Terraform resources. One per manifest; the processor ID
#    lives in Terraform state and is handed to the script with --dest-processor.
#    display_name and type are immutable: changing either in a manifest would recreate the
#    processor and lose its versions. prevent_destroy turns that, and the removal of a manifest,
#    into a plan error instead. For a throwaway test environment, set it to false to allow
#    `terraform destroy`.
resource "google_document_ai_processor" "managed" {
  for_each     = local.native_processors
  project      = var.destination_project_id
  location     = try(each.value.location, var.destination_location)
  display_name = try(each.value.display_name, each.key)
  type         = try(each.value.processor_type, "CUSTOM_EXTRACTION_PROCESSOR")

  lifecycle {
    prevent_destroy = true
  }
}

# Day 0 adoption: a manifest that names an already-existing destination processor
# (existing_processor_id: "<id>") is imported into state instead of being created.
# Remove the field from the manifest after the first successful apply.
import {
  for_each = {
    for k, m in local.native_processors : k => m if try(m.existing_processor_id, "") != ""
  }
  to = google_document_ai_processor.managed[each.key]
  id = "projects/${var.destination_project_id}/locations/${try(each.value.location, var.destination_location)}/processors/${each.value.existing_processor_id}"
}

# 5. Trigger per-processor reconciliation (only re-runs when Git manifest, version, schema.json hash, or script changes)
#    Step 7 of the script, "verify the copy", reads the destination back and checks it against the
#    source (type, dataset schema vs the Git schema file, pinned version present, deployed, name, not
#    the pretrained model, same base model, the schema inside the version) BEFORE step 8 makes it the
#    default. A failed check exits 3 without switching the default, which fails this provisioner and
#    therefore the apply - the CI run goes red, production keeps its current default, and the next
#    apply re-runs the copy and the checks. Nothing else to wire.
resource "terraform_data" "promote" {
  for_each = local.processors

  depends_on = [
    google_project_iam_member.source_docai_editor,
    google_project_iam_member.source_storage_viewer,
    google_storage_bucket.dest_dataset
  ]

  triggers_replace = [
    var.force_reconcile ? timestamp() : "declarative",
    each.value.source_processor_id,
    var.destination_project_id,
    each.value.destination_location,
    # Native mode: the processor ID comes from state, so a recreated processor also re-runs the promotion.
    try(google_document_ai_processor.managed[each.key].id, each.value.destination_processor_id),
    each.value.destination_display_name,
    each.value.versions_mode,
    each.value.specific_version_id,
    tostring(each.value.deploy_version),
    tostring(each.value.set_default_version),
    tostring(each.value.copy_dataset),
    each.value.schema_file != "" ? filesha256("${path.module}/${each.value.schema_file}") : "live-source-schema",
    filesha256("${path.module}/scripts/copy_processor.py")
  ]

  # Dependencies are NOT installed here. With for_each, up to ten of these run in parallel and a
  # shared `.venv` would race. Install `scripts/requirements.txt` once on the runner instead
  # (the GitHub Actions workflow does this; locally run `pip install -r scripts/requirements.txt`).
  provisioner "local-exec" {
    command = <<-EOT
      export GOOGLE_CLOUD_QUOTA_PROJECT="${var.destination_project_id}"
      export CLOUDSDK_CORE_PROJECT="${var.destination_project_id}"
      ${var.python_bin} ${path.module}/scripts/copy_processor.py \
        --source-processor "${each.value.source_processor_id}" \
        --dest-project "${var.destination_project_id}" \
        --dest-location "${each.value.destination_location}" \
        ${try(google_document_ai_processor.managed[each.key].id, each.value.destination_processor_id) != "" ? "--dest-processor \"${try(google_document_ai_processor.managed[each.key].id, each.value.destination_processor_id)}\"" : ""} \
        ${each.value.destination_display_name != "" ? "--dest-display-name \"${each.value.destination_display_name}\"" : ""} \
        ${each.value.specific_version_id != "" ? "--version-id \"${each.value.specific_version_id}\"" : "--versions ${each.value.versions_mode}"} \
        ${each.value.deploy_version ? "--deploy" : ""} \
        ${each.value.set_default_version ? "--set-default" : ""} \
        ${each.value.copy_dataset ? "--copy-dataset --dest-dataset-bucket \"${each.value.destination_dataset_bucket}\"" : ""} \
        ${each.value.allow_dataset_purge ? "--allow-dataset-purge" : ""} \
        ${each.value.schema_file != "" ? "--schema-file \"${path.module}/${each.value.schema_file}\"" : ""} \
        ${each.value.export_schema_path != "" ? "--export-schema \"${path.module}/${each.value.export_schema_path}\"" : ""} \
        --source-project-id "${each.value.source_project_id}" \
        ${var.version_map_uri != "" ? "--version-map \"${var.version_map_uri}\"" : ""} \
        ${var.bigquery_dataset_id != "" && var.bigquery_table_id != "" ? "--bigquery-project \"${each.value.source_project_id}\" --bigquery-dataset-id \"${var.bigquery_dataset_id}\" --bigquery-table-id \"${var.bigquery_table_id}\"" : ""}
    EOT
  }
}
