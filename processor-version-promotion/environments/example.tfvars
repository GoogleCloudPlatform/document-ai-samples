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

# environments/example.tfvars — copy to environments/<env>.tfvars (for example qa.tfvars) and set the
# values. bootstrap/setup_cicd.sh --env <env> writes the same file for you.
# One environment = one destination project. Sources are declared per processor in manifests_dir.
#
#   terraform plan -var-file=environments/qa.tfvars          (workstation / Cloud Shell)
#   GitHub Actions: plan.yml / apply.yml pass the same -var-file per matrix entry
#
# Nothing here is secret. Credentials never go here (the identity lives in the CI system), nor does
# anything per processor (that is the manifest).

destination_project_id = "my-qa-project"
destination_location   = "us" # Document AI location of the destination processors: us or eu

# Processor manifests promoted into this environment: one *.yaml per processor,
# written by `scripts/export_processor.py --env qa`.
manifests_dir = "manifests/qa"

# Memory of which destination version came from which source version
# (see VersionMap in scripts/copy_processor.py). Recommended: a prefix in the state bucket.
version_map_uri = "gs://my-qa-project-tfstate/qa/version_map"

# Run log: one BigQuery row per run, in the SOURCE project. Set bigquery_dataset_id = "" to turn it off.
bigquery_dataset_id = "docai_migration_logs"
bigquery_table_id   = "migration_events"

# Interpreter that runs scripts/copy_processor.py (scripts/requirements.txt installed for it).
python_bin = "python3"

# true = re-run every processor on the next apply even if nothing changed in Git (one-off repair; set back to false).
force_reconcile = false
