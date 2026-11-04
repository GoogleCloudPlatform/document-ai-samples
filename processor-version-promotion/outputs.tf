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

output "destination_project" {
  value = var.destination_project_id
}

output "service_agent_authorized" {
  value = local.dest_docai_sa
}

output "managed_processors" {
  description = "Map of processor keys managed in this Terraform workspace and their source/schema settings"
  value = {
    for k, p in local.processors : k => {
      source_processor = p.source_processor_id
      display_name     = p.destination_display_name
      schema_file      = p.schema_file
      version_id       = p.specific_version_id != "" ? p.specific_version_id : p.versions_mode
    }
  }
}
output "processor_ids" {
  description = "Destination processor resource names created or adopted by Terraform (manifest mode with manage_processors_natively = true)"
  value       = { for k, p in google_document_ai_processor.managed : k => p.id }
}
