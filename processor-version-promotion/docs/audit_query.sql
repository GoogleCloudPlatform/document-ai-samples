-- Copyright 2026 Google LLC
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     https://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.

-- Document AI promotion audit log: one row per pipeline run (copy_processor.py writes it).
-- BigQuery console → paste → Run, or save as "docai promotion audit".
-- PROJECT below is the project the rows are written to: the value of --bigquery-project
-- (main.tf passes the training (source) project).
--
-- What to point at:
--   version_action   imported = model copied once; reused = pointer moved (promotion of a known
--                    version, or a revert); adopted = Day 0 took over an existing version
--   dataset_copied   false on every row: no documents leave the training project
--   destination_processor_id constant while destination_version_id changes: the endpoint is stable

SELECT
  FORMAT_TIMESTAMP('%m-%d %H:%M', execution_timestamp) AS at_utc,
  destination_project_id                              AS project,
  destination_processor_name                          AS processor,
  version_action,
  source_version_id,
  destination_version_id,
  destination_processor_id,
  execution_status,
  dataset_copied
FROM `PROJECT.docai_migration_logs.migration_events`
ORDER BY execution_timestamp DESC
LIMIT 15;
