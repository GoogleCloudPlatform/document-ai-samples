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

variable "source_project_id" {
  description = "GCP Project ID hosting the source processor"
  type        = string
  default     = ""
}

variable "source_processor_id" {
  description = "Full resource name of the source processor (e.g. projects/123/locations/us/processors/abc). Optional when manifests_dir is used."
  type        = string
  default     = ""
}

variable "destination_project_id" {
  description = "GCP Project ID where processor(s) will be migrated (can be the same project or cross-project)"
  type        = string
}

variable "destination_location" {
  description = "Location for destination processor (e.g. 'us' or 'eu')"
  type        = string
  default     = "us"
}

variable "destination_processor_id" {
  description = "Optional existing processor resource name or ID. If left empty, a new processor is automatically created."
  type        = string
  default     = ""
}

variable "destination_display_name" {
  description = "Display name for newly created destination processor"
  type        = string
  default     = ""
}

variable "versions_mode" {
  description = "Versions to copy: 'default' or 'all'"
  type        = string
  default     = "default"
}

variable "specific_version_id" {
  description = "Specific version ID to copy (overrides versions_mode)"
  type        = string
  default     = ""
}

variable "deploy_version" {
  description = "Deploy the migrated version"
  type        = bool
  default     = true
}

variable "set_default_version" {
  description = "Set the imported version as default. Requires deploy_version = true unless the version is already deployed in the destination."
  type        = bool
  default     = true
}

variable "copy_dataset" {
  description = "Whether to migrate training/test documents and dataset"
  type        = bool
  default     = false
}

variable "allow_dataset_purge" {
  description = "Allow purging an existing non-empty destination dataset after backing up its schema and split documents to GCS"
  type        = bool
  default     = false
}

variable "destination_dataset_bucket" {
  description = "GCS bucket name for destination dataset storage and restorable snapshots (required if copy_dataset is true)"
  type        = string
  default     = ""
}

variable "schema_file" {
  description = "Optional path (relative to repo root) to a Git-tracked DocumentSchema JSON file (e.g. 'schemas/invoice_extractor.schema.json'). When set, destination schema is defined from this file and changes trigger Terraform apply."
  type        = string
  default     = ""
}

variable "export_schema_path" {
  description = "Optional path (relative to repo root) where the source processor's schema will be exported as deterministic JSON for Git tracking."
  type        = string
  default     = ""
}

variable "manifests_dir" {
  description = "Optional directory (relative to repo root, e.g. 'manifests/qa' or 'manifests/example') containing per-processor *.yaml manifests for multi-processor orchestration via for_each."
  type        = string
  default     = ""
}

variable "force_reconcile" {
  description = "When true, forces local-exec migration to run on every terraform apply even if Git hashes have not changed."
  type        = bool
  default     = false
}

variable "bigquery_dataset_id" {
  description = "BigQuery dataset (in the source project) for the migration run log. Created if missing. Set to \"\" to disable logging."
  type        = string
  default     = "docai_migration_logs"
}

variable "bigquery_table_id" {
  description = "BigQuery table for the migration run log (one row per run). Created if missing. Set to \"\" to disable logging."
  type        = string
  default     = "migration_events"
}
variable "manage_processors_natively" {
  description = "Manifest mode only. When true, each destination processor is a google_document_ai_processor resource (ID kept in Terraform state) and the script receives it via --dest-processor. Processors that already exist must be adopted once with existing_processor_id in their manifest. When false, the script creates processors itself (legacy behaviour)."
  type        = bool
  default     = true
}

variable "python_bin" {
  description = "Python interpreter used by the local-exec provisioner. Dependencies from scripts/requirements.txt must already be installed for it."
  type        = string
  default     = "python3"
}

variable "version_map_uri" {
  description = <<-EOT
    Where copy_processor.py keeps its source->destination version-id map (one JSON per destination
    processor). Recommended: a prefix in the Terraform state bucket, next to this environment's state,
    e.g. "gs://<project>-tfstate/<env>/version_map". A local directory works for laptop runs
    (e.g. ".version_map", git-ignored). Empty disables the map: versions are then matched by display
    name only, which cannot tell two versions with the same name apart.
  EOT
  type        = string
  default     = ""
}
