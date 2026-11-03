#!/usr/bin/env python3
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

"""
Document AI Cross-Project & Same-Project Migration Script with:
- Automated ADC quota project configuration (zero manual intervention)
- Unconditional destination dataset initialization right after processor creation
- Full Schema Migration preserving field descriptions and enabled/disabled states
- Destination dataset backup to GCS and purge before re-importing
- Safe BatchDeleteDocuments & ImportDocuments LRO polling (avoids SDK proto unpacking bug)
- Exact Train/Test/Unassigned split preservation (no 80:20 auto-split)
- Auto-detects & reuses created destination processor on retries
- Robust asynchronous deployment waiting with retry/poll logic before setting default
- Verifies the copy (eight read-only checks) before it becomes the default; a failed check
  leaves the processor's current default untouched
- Logs one row per run (success, completed with errors, or failed) to a BigQuery table
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Optional

_RUN_T0 = time.monotonic()  # process start, for the total in the final banner


def _elapsed(t0: float) -> str:
    """Human-readable wall-clock since t0, e.g. '4m 31s' or '38s'."""
    secs = int(time.monotonic() - t0)
    return f"{secs // 60}m {secs % 60:02d}s" if secs >= 60 else f"{secs}s"

from google.api_core.client_options import ClientOptions
from google.api_core import exceptions as gexc
from google.api_core.exceptions import GoogleAPICallError, NotFound, PermissionDenied
from google.cloud import bigquery
from google.cloud import documentai_v1beta3 as docai
from google.cloud import resourcemanager_v3
from google.cloud import storage
from google.protobuf import field_mask_pb2

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def log_pass(msg: str):
    print(f"  {GREEN}[PASSED]{RESET} {msg}")


def log_fail(msg: str):
    print(f"  {RED}[FAILED]{RESET} {msg}")


def log_info(msg: str):
    print(f"  {CYAN}[INFO]{RESET} {msg}")


def log_check(msg: str):
    print(f"{BOLD}[CHECK]{RESET} {msg}")


# Errors that should not stop the migration mid-way, but must prevent a false
# "success" result. Collected during the run and reported at the end of main(),
# which then exits with code 3 instead of 0.
DEFERRED_ERRORS: list[str] = []


def log_deferred_error(msg: str):
    """Logs a failure in red and records it so the run ends with exit code 3."""
    log_fail(msg)
    DEFERRED_ERRORS.append(msg)


def with_retries(fn, label: str, attempts: int = 3, base_delay: float = 2.0):
    """Calls fn(), retrying on any exception with exponential backoff.

    Re-raises the last exception if all attempts fail.
    """
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:
            if attempt == attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            log_info(f"Retrying {label} (attempt {attempt}/{attempts} failed: {e}); waiting {delay:.0f}s...")
            time.sleep(delay)


_IMPORTABLE_STATES = {
    docai.ProcessorVersion.State.DEPLOYED,
    docai.ProcessorVersion.State.UNDEPLOYED,
}

_SPLIT_NAMES = (
    "DATASET_SPLIT_TRAIN",
    "DATASET_SPLIT_TEST",
    "DATASET_SPLIT_UNASSIGNED",
)

_PROCESSOR_RE = re.compile(
    r"^projects/(?P<project>[^/]+)/locations/(?P<location>[^/]+)/processors/(?P<processor_id>[^/]+)$"
)


def load_manifest_file(path: str) -> dict[str, Any]:
    """Loads a processor manifest from YAML or JSON without requiring external packages."""
    raw = Path(path).read_text(encoding="utf-8")
    if path.endswith(".json"):
        return json.loads(raw)
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(raw)
        return data if isinstance(data, dict) else {}
    except ImportError:
        pass

    # Lightweight parser for flat key: value YAML manifests when PyYAML is not installed
    result: dict[str, Any] = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, val = stripped.split(":", 1)
        key = key.strip()
        val = val.split("#", 1)[0].strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        elif val.lower() in ("true", "false"):
            result[key] = val.lower() == "true"
            continue
        elif val.lower() in ("null", "none", "~", ""):
            result[key] = None
            continue
        else:
            try:
                result[key] = int(val)
                continue
            except ValueError:
                pass
        result[key] = val
    return result


@dataclass
class ProcessorRef:
    project: str
    location: str
    processor_id: str

    @property
    def name(self) -> str:
        return f"projects/{self.project}/locations/{self.location}/processors/{self.processor_id}"


def parse_processor(
    name: str,
    default_project: Optional[str] = None,
    default_location: Optional[str] = None,
) -> ProcessorRef:
    name = name.strip()
    m = _PROCESSOR_RE.match(name)
    if m:
        return ProcessorRef(**m.groupdict())
    if default_project and default_location and "/" not in name:
        return ProcessorRef(
            project=default_project,
            location=default_location,
            processor_id=name,
        )
    raise ValueError(
        f"Invalid processor format: {name!r}. Expected: "
        f"projects/{{project}}/locations/{{location}}/processors/{{id}}"
    )


def parse_gcs_uri(uri: str) -> tuple[str, str]:
    """Splits 'gs://bucket/optional/prefix' into (bucket, prefix_without_trailing_slash)."""
    clean = uri.strip()
    if clean.startswith("gs://"):
        clean = clean[len("gs://") :]
    clean = clean.strip("/")
    if "/" in clean:
        bucket, prefix = clean.split("/", 1)
        return bucket, prefix.strip("/")
    return clean, ""


def docai_endpoint(location: str) -> str:
    return f"{location}-documentai.googleapis.com"


def client_for(
    location: str, quota_project_id: Optional[str] = None
) -> docai.DocumentProcessorServiceClient:
    return docai.DocumentProcessorServiceClient(
        client_options=ClientOptions(
            api_endpoint=docai_endpoint(location),
            quota_project_id=quota_project_id,
        )
    )


def dataset_client_for(
    location: str, quota_project_id: Optional[str] = None
) -> docai.DocumentServiceClient:
    return docai.DocumentServiceClient(
        client_options=ClientOptions(
            api_endpoint=docai_endpoint(location),
            quota_project_id=quota_project_id,
        )
    )


def run_preflight_checks(
    src: ProcessorRef,
    dest_project_id: str,
    dest_location: str,
    copy_dataset: bool,
    dest_dataset_bucket: Optional[str],
) -> tuple[str, str]:
    print(f"\n{BOLD}{'=' * 75}{RESET}")
    print(f"{BOLD}   DOCUMENT AI MIGRATION: PRE-FLIGHT PERMISSION CHECKS{RESET}")
    print(f"{BOLD}{'=' * 75}{RESET}")

    all_passed = True
    rm_client = resourcemanager_v3.ProjectsClient(
        client_options=ClientOptions(quota_project_id=dest_project_id)
    )

    log_check("Resolving destination project details and service agent...")
    try:
        dest_proj_res = rm_client.get_project(name=f"projects/{dest_project_id}")
        dest_project_number = dest_proj_res.name.split("/")[-1]
        dest_service_agent = f"service-{dest_project_number}@gcp-sa-prod-dai-core.iam.gserviceaccount.com"
        log_pass("Caller authenticated and destination project resolved.")
        log_info(f"Destination Project Number: {dest_project_number}")
        log_info(f"Destination Document AI Service Agent: {dest_service_agent}")
    except Exception as e:
        log_fail(f"Could not access destination project '{dest_project_id}': {e}")
        # Every remaining check depends on the destination service agent resolved above,
        # so there is nothing further to verify. Fail preflight immediately.
        print(f"{BOLD}{'=' * 75}{RESET}")
        print(f"{RED}{BOLD}PRE-FLIGHT CHECKS FAILED. Cannot resolve destination project.{RESET}\n")
        sys.exit(2)

    log_check(f"Checking permissions on SOURCE project [{src.project}]...")
    src_client = client_for(src.location, quota_project_id=dest_project_id)
    try:
        src_client.get_processor(name=src.name)
        log_pass(f"Caller has read permissions for processor: {src.processor_id}")
    except PermissionDenied:
        log_fail(f"Caller lacks 'roles/documentai.viewer' on source project [{src.project}].")
        all_passed = False
    except NotFound:
        log_fail(f"Source processor not found: {src.name}")
        all_passed = False
    except Exception as e:
        log_fail(f"Source processor verification failed: {e}")
        all_passed = False

    if src.project != dest_project_id:
        log_check("Verifying Cross-Project Document AI Service Agent IAM...")
        # Reading the source project's IAM policy needs resourcemanager.projects.getIamPolicy, which
        # roles/documentai.viewer (the only role the pipeline SA holds on the source) does not
        # include. The check is advisory: ImportProcessorVersion is the authoritative test and
        # fails fast with a 403 naming the service agent if the grant is missing.
        try:
            source_policy = rm_client.get_iam_policy(resource=f"projects/{src.project}")
            sa_member_str = f"serviceAccount:{dest_service_agent}"
            valid_roles = {
                "roles/documentai.editor",
                "roles/documentai.admin",
                "roles/editor",
                "roles/owner",
            }
            sa_roles = [
                b.role
                for b in source_policy.bindings
                if sa_member_str in b.members and b.role in valid_roles
            ]
            if len(sa_roles) > 0:
                first_role = sa_roles[0]
                log_pass(f"Destination Service Agent has sufficient role on source project: {first_role}")
            else:
                log_fail(
                    f"Destination Service Agent {dest_service_agent} lacks Document AI Editor role on source project."
                )
                all_passed = False
        except PermissionDenied:
            print(
                f"  {YELLOW}[SKIPPED]{RESET} Caller cannot read the IAM policy of source project [{src.project}] "
                f"(no resourcemanager.projects.getIamPolicy; expected with roles/documentai.viewer only). "
                f"Required grant, made by the source project owner: roles/documentai.editor -> {dest_service_agent}. "
                f"ImportProcessorVersion will fail with 403 if it is missing."
            )
        except Exception as e:
            log_fail(f"Could not inspect source project IAM policy: {e}")
            all_passed = False
    else:
        log_info("Source and destination project are the same. Skipping cross-project Service Agent IAM check.")

    log_check(f"Checking permissions on DESTINATION project [{dest_project_id}]...")
    dst_client = client_for(dest_location, quota_project_id=dest_project_id)
    try:
        dst_client.list_processors(parent=f"projects/{dest_project_id}/locations/{dest_location}")
        log_pass("Caller has Document AI administrative permissions on destination project.")
    except PermissionDenied:
        log_fail(f"Caller lacks Document AI permissions on destination project [{dest_project_id}].")
        all_passed = False
    except Exception as e:
        log_fail(f"Destination permissions check failed: {e}")
        all_passed = False

    if copy_dataset:
        log_check("Checking Dataset Storage & GCS Permissions...")
        if not dest_dataset_bucket:
            log_fail("--dest-dataset-bucket is required when --copy-dataset is active.")
            all_passed = False
        else:
            try:
                storage_client = storage.Client(
                    project=dest_project_id,
                    client_options=ClientOptions(quota_project_id=dest_project_id),
                )
                clean_dest, _ = parse_gcs_uri(dest_dataset_bucket)
                bucket = storage_client.lookup_bucket(clean_dest)
                if bucket:
                    log_pass(f"Destination GCS Bucket 'gs://{clean_dest}' verified and accessible.")
                else:
                    log_info(f"Destination GCS Bucket 'gs://{clean_dest}' will be created by Terraform.")
            except Exception as e:
                log_fail(f"GCS check failed: {e}")
                all_passed = False

    print(f"{BOLD}{'=' * 75}{RESET}")
    if not all_passed:
        print(f"{RED}{BOLD}PRE-FLIGHT CHECKS FAILED. Correct permissions above.{RESET}\n")
        sys.exit(2)

    print(f"{GREEN}{BOLD}ALL PRE-FLIGHT CHECKS PASSED! STARTING MIGRATION WORKFLOW...{RESET}")
    print(f"{BOLD}{'=' * 75}{RESET}\n")
    return dest_project_number, dest_service_agent


def is_versioned_foundation(version: docai.ProcessorVersion) -> bool:
    info = version.gen_ai_model_info
    custom_type = info.custom_gen_ai_model_info.custom_model_type if info else None
    _type_enum = docai.ProcessorVersion.GenAiModelInfo.CustomGenAiModelInfo.CustomModelType
    if custom_type == _type_enum.VERSIONED_FOUNDATION:
        return True
    if (
        version.model_type == docai.ProcessorVersion.ModelType.MODEL_TYPE_GENERATIVE
        and custom_type != _type_enum.FINE_TUNED
    ):
        return True
    return False


def ensure_destination_dataset_initialized(
    dataset_client: docai.DocumentServiceClient,
    dest_dataset_name: str,
    dry_run: bool,
) -> None:
    """Initializes unmanaged dataset on the destination processor with safe polling."""
    if dry_run:
        print(f"[dry-run] Would initialize dataset {dest_dataset_name}")
        return
    log_check(f"Initializing dataset on destination processor ({dest_dataset_name})...")
    try:
        dataset_obj = docai.Dataset(
            name=dest_dataset_name,
            unmanaged_dataset_config=docai.Dataset.UnmanagedDatasetConfig(),
        )
        update_mask = field_mask_pb2.FieldMask(paths=["unmanaged_dataset_config"])
        init_req = docai.UpdateDatasetRequest(dataset=dataset_obj, update_mask=update_mask)
        op = dataset_client.update_dataset(request=init_req)
        print("  Waiting for dataset initialization LRO to complete...")

        # Safe poll avoiding SDK Empty proto deserialization warning
        op_name = op.operation.name
        ops_client = dataset_client.transport.operations_client
        max_wait = 300
        poll_start = time.time()

        while time.time() - poll_start < max_wait:
            raw_op = ops_client.get_operation(op_name)
            if raw_op.done:
                if raw_op.error and raw_op.error.code != 0:
                    raise RuntimeError(f"Initialization failed: {raw_op.error.message}")
                break
            time.sleep(3)
        else:
            raise TimeoutError(f"Dataset initialization did not complete within {max_wait}s (operation {op_name}).")

        log_pass("Destination dataset initialized successfully.")
    except Exception as e:
        err_msg = str(e)
        if "already" in err_msg.lower():
            log_pass("Destination dataset is already initialized.")
        else:
            # Without an initialized dataset, the schema copy and document import that
            # follow cannot succeed. Stop here with a clear error.
            raise RuntimeError(f"Destination dataset initialization failed: {err_msg}") from e


def normalize_document_schema(src_doc_schema: docai.DocumentSchema) -> docai.DocumentSchema:
    """Rebuilds a clean DocumentSchema preserving all fields, descriptions, and active/inactive states."""
    new_entity_types = []
    for et in src_doc_schema.entity_types:
        copied_properties = []
        for prop in et.properties:
            copied_prop = docai.DocumentSchema.EntityType.Property(
                name=prop.name,
                display_name=prop.display_name,
                description=prop.description,
                value_type=prop.value_type,
                occurrence_type=prop.occurrence_type,
                method=prop.method,
                property_metadata=docai.PropertyMetadata(
                    inactive=prop.property_metadata.inactive if prop.property_metadata else False
                ),
            )
            copied_properties.append(copied_prop)

        copied_et = docai.DocumentSchema.EntityType(
            name=et.name,
            display_name=et.display_name,
            description=et.description,
            base_types=list(et.base_types),
            properties=copied_properties,
            entity_type_metadata=docai.EntityTypeMetadata(
                inactive=et.entity_type_metadata.inactive if et.entity_type_metadata else False
            ),
        )
        if hasattr(et, "enum_values") and et.enum_values:
            copied_et.enum_values = et.enum_values
        new_entity_types.append(copied_et)

    return docai.DocumentSchema(
        display_name=src_doc_schema.display_name,
        description=src_doc_schema.description,
        entity_types=new_entity_types,
        metadata=src_doc_schema.metadata,
        document_prompt=src_doc_schema.document_prompt if hasattr(src_doc_schema, "document_prompt") else "",
    )


def document_schema_to_canonical_json(doc_schema: docai.DocumentSchema) -> str:
    """Serializes a DocumentSchema to deterministic, Git-friendly JSON (sorted keys, 2-space indent)."""
    raw_json = docai.DocumentSchema.to_json(
        normalize_document_schema(doc_schema),
        preserving_proto_field_name=True,
    )
    parsed = json.loads(raw_json)
    return json.dumps(parsed, indent=2, sort_keys=True) + "\n"


def export_schema_to_file(
    dataset_client: docai.DocumentServiceClient,
    proc_ref: ProcessorRef,
    output_path: str,
) -> docai.DocumentSchema:
    """Fetches a processor's DatasetSchema and writes deterministic JSON to output_path for Git tracking."""
    schema_name = dataset_client.dataset_schema_path(proc_ref.project, proc_ref.location, proc_ref.processor_id)
    log_info(f"Fetching dataset schema from {schema_name}...")
    schema_obj = dataset_client.get_dataset_schema(name=schema_name)
    canonical_json = document_schema_to_canonical_json(schema_obj.document_schema)

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(canonical_json, encoding="utf-8")
    n_props = sum(len(et.properties) for et in schema_obj.document_schema.entity_types)
    log_pass(
        f"Exported schema ({len(schema_obj.document_schema.entity_types)} entity types, "
        f"{n_props} properties) to {out_file}"
    )
    return schema_obj.document_schema


def load_schema_from_file(schema_file_path: str) -> docai.DocumentSchema:
    """Loads a Git-tracked DocumentSchema JSON file."""
    path = Path(schema_file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Schema file not found: {schema_file_path}")
    raw_text = path.read_text(encoding="utf-8")
    loaded = docai.DocumentSchema.from_json(raw_text, ignore_unknown_fields=True)
    return normalize_document_schema(loaded)


def copy_dataset_schema(
    dataset_client: docai.DocumentServiceClient,
    src: ProcessorRef,
    dest_ref: ProcessorRef,
    dry_run: bool,
    schema_file: Optional[str] = None,
    export_schema_path: Optional[str] = None,
) -> None:
    dst_schema_name = dataset_client.dataset_schema_path(dest_ref.project, dest_ref.location, dest_ref.processor_id)

    if schema_file:
        log_info(f"Loading desired dataset schema from Git-tracked file: {schema_file}...")
        new_document_schema = load_schema_from_file(schema_file)
        if export_schema_path:
            out_file = Path(export_schema_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(document_schema_to_canonical_json(new_document_schema), encoding="utf-8")
            log_pass(f"Wrote canonical schema to {out_file}")
    else:
        src_schema_name = dataset_client.dataset_schema_path(src.project, src.location, src.processor_id)
        log_info(f"Retrieving source dataset schema from {src_schema_name}...")
        src_client = dataset_client_for(src.location, quota_project_id=dest_ref.project)
        source_schema_obj = src_client.get_dataset_schema(name=src_schema_name)
        new_document_schema = normalize_document_schema(source_schema_obj.document_schema)
        if export_schema_path:
            out_file = Path(export_schema_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(document_schema_to_canonical_json(new_document_schema), encoding="utf-8")
            log_pass(f"Exported source schema to {out_file} for Git tracking.")

    n_props = sum(len(et.properties) for et in new_document_schema.entity_types)
    print(
        f"Applying complete schema ({len(new_document_schema.entity_types)} entity types, "
        f"{n_props} fields, descriptions, active/inactive states)..."
    )

    if dry_run:
        print(f"[dry-run] Would replace schema on destination: {dst_schema_name}")
        return

    # Save a local pre-change backup of the destination schema before overwriting so
    # accidental schema edits can always be reverted even if copy_dataset is false.
    try:
        current_dst_schema = dataset_client.get_dataset_schema(name=dst_schema_name)
        current_json = document_schema_to_canonical_json(current_dst_schema.document_schema)
        desired_json = document_schema_to_canonical_json(new_document_schema)
        if current_json == desired_json:
            log_pass("Destination dataset schema already matches desired schema (no-op).")
            return
        if current_dst_schema.document_schema.entity_types:
            ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_dir = Path(".schema_backups")
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_file = backup_dir / f"{dest_ref.processor_id}_{ts}.schema.json"
            backup_file.write_text(current_json, encoding="utf-8")
            log_info(f"Backed up previous destination schema to {backup_file}")
    except Exception as e:
        log_info(f"Could not read existing destination schema for pre-change diff ({e}); proceeding with update.")

    dataset_client.update_dataset_schema(
        dataset_schema=docai.DatasetSchema(name=dst_schema_name, document_schema=new_document_schema),
        update_mask=field_mask_pb2.FieldMask(paths=["document_schema"]),
    )
    log_pass("Destination dataset schema copied and replaced successfully.")


def _split_name_for_doc(doc_meta: docai.DocumentMetadata) -> str:
    if hasattr(doc_meta, "dataset_type") and doc_meta.dataset_type:
        split_enum = doc_meta.dataset_type
        if split_enum == docai.DatasetSplitType.DATASET_SPLIT_TRAIN:
            return "DATASET_SPLIT_TRAIN"
        if split_enum == docai.DatasetSplitType.DATASET_SPLIT_TEST:
            return "DATASET_SPLIT_TEST"
    return "DATASET_SPLIT_UNASSIGNED"


def snapshot_processor_to_gcs(
    dataset_client: docai.DocumentServiceClient,
    storage_client: storage.Client,
    proc_ref: ProcessorRef,
    gcs_uri_prefix: str,
    dry_run: bool,
) -> dict[str, Any]:
    """Exports a full restorable snapshot (schema + split-categorized documents + manifest) to GCS."""
    clean_bucket, prefix = parse_gcs_uri(gcs_uri_prefix)
    if not prefix:
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        prefix = f"snapshots/{proc_ref.processor_id}/{ts}"
    bucket = storage_client.bucket(clean_bucket)
    dataset_name = f"{proc_ref.name}/dataset"
    schema_name = dataset_client.dataset_schema_path(proc_ref.project, proc_ref.location, proc_ref.processor_id)

    log_check(f"Creating restorable snapshot of {proc_ref.name} to gs://{clean_bucket}/{prefix}/...")

    # 1. Snapshot dataset_schema.json
    schema_obj = dataset_client.get_dataset_schema(name=schema_name)
    schema_json = document_schema_to_canonical_json(schema_obj.document_schema)
    if not dry_run:
        schema_blob = bucket.blob(f"{prefix}/dataset_schema.json")
        schema_blob.upload_from_string(schema_json, content_type="application/json")
    log_pass(f"Saved dataset_schema.json to gs://{clean_bucket}/{prefix}/dataset_schema.json")

    # 2. List and export documents into DATASET_SPLIT_TRAIN / TEST / UNASSIGNED subfolders
    try:
        list_req = docai.ListDocumentsRequest(dataset=dataset_name, page_size=100, return_total_size=True)
        docs = list(dataset_client.list_documents(request=list_req))
    except NotFound:
        docs = []

    split_counts = {k: 0 for k in _SPLIT_NAMES}
    failed_backups: list[str] = []

    for idx, doc_meta in enumerate(docs):
        split_name = _split_name_for_doc(doc_meta)
        doc_label = getattr(doc_meta.document_id.unmanaged_doc_id, "doc_id", None) or f"doc_{idx}"
        object_path = f"{prefix}/{split_name}/{doc_label}.json"

        if not dry_run:
            def _backup_one(doc_meta=doc_meta, object_path=object_path):
                get_doc_req = docai.GetDocumentRequest(dataset=dataset_name, document_id=doc_meta.document_id)
                doc_response = dataset_client.get_document(request=get_doc_req)
                doc_json = docai.Document.to_json(doc_response.document)
                blob = bucket.blob(object_path)
                blob.upload_from_string(doc_json, content_type="application/json")

            try:
                with_retries(_backup_one, label=f"snapshot of document {doc_label}")
            except Exception as e:
                log_fail(f"Snapshot failed for document {doc_label} after retries: {e}")
                failed_backups.append(doc_label)
                continue

        split_counts[split_name] += 1

    if not dry_run and docs:
        backed_up_count = sum(
            1
            for b in storage_client.list_blobs(clean_bucket, prefix=f"{prefix}/")
            if any(b.name.startswith(f"{prefix}/{sp}/") for sp in _SPLIT_NAMES)
        )
        if failed_backups or backed_up_count != len(docs):
            raise RuntimeError(
                f"Snapshot incomplete ({backed_up_count}/{len(docs)} documents in "
                f"gs://{clean_bucket}/{prefix}/). Failed: {failed_backups or 'none reported'}."
            )

    manifest = {
        "snapshot_timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "processor_name": proc_ref.name,
        "processor_id": proc_ref.processor_id,
        "gcs_snapshot_uri": f"gs://{clean_bucket}/{prefix}",
        "total_documents": len(docs),
        "split_counts": split_counts,
        "entity_type_count": len(schema_obj.document_schema.entity_types),
    }
    if not dry_run:
        manifest_blob = bucket.blob(f"{prefix}/snapshot_manifest.json")
        manifest_blob.upload_from_string(json.dumps(manifest, indent=2) + "\n", content_type="application/json")

    log_pass(
        f"Snapshot complete at gs://{clean_bucket}/{prefix}/ "
        f"(splits: {split_counts}).\n"
        f"  To restore this snapshot later, run:\n"
        f"    python3 scripts/copy_processor.py --dest-project {proc_ref.project} "
        f"--dest-location {proc_ref.location} --dest-processor {proc_ref.name} "
        f"--restore-from-gcs gs://{clean_bucket}/{prefix} --allow-dataset-purge"
    )
    return manifest


def backup_and_purge_destination_dataset(
    dataset_client: docai.DocumentServiceClient,
    storage_client: storage.Client,
    dest_dataset_name: str,
    dest_bucket_name: str,
    dest_processor_id: str,
    dry_run: bool,
    dest_ref: Optional[ProcessorRef] = None,
    allow_dataset_purge: bool = True,
) -> None:
    clean_bucket, _ = parse_gcs_uri(dest_bucket_name)

    try:
        list_req = docai.ListDocumentsRequest(dataset=dest_dataset_name, page_size=100, return_total_size=True)
        dest_docs = list(dataset_client.list_documents(request=list_req))
    except NotFound:
        log_info("Destination dataset has no existing documents to purge.")
        return
    except GoogleAPICallError as e:
        if dry_run:
            # In a dry run the destination processor may not exist yet (placeholder ID),
            # so a listing error is expected and there is nothing to purge.
            log_info(f"[dry-run] Could not list destination dataset ({e}). Assuming nothing to purge.")
            return
        # Any other API error means we can't tell what is in the destination. Stop rather
        # than skip the purge and import on top of existing documents (duplicates).
        raise RuntimeError(f"Could not list destination dataset documents for purge: {e}") from e

    if not dest_docs:
        log_info("Destination dataset is currently empty. No documents to purge.")
        return

    if not allow_dataset_purge:
        raise RuntimeError(
            f"Destination dataset {dest_dataset_name} already contains {len(dest_docs)} document(s), "
            "and --allow-dataset-purge was not set. Refusing to overwrite existing dataset. "
            "Pass --allow-dataset-purge to back up to GCS and replace the destination dataset."
        )

    # Use timezone-aware UTC datetime and save a full split-preserving snapshot (schema + splits)
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_prefix = f"backup-destination-dataset-{dest_processor_id}-{timestamp}"
    target_ref = dest_ref or parse_processor(dest_dataset_name[: -len("/dataset")])
    snapshot_processor_to_gcs(
        dataset_client=dataset_client,
        storage_client=storage_client,
        proc_ref=target_ref,
        gcs_uri_prefix=f"gs://{clean_bucket}/{backup_prefix}",
        dry_run=dry_run,
    )

    print(f"Purging {len(dest_docs)} existing document(s) from destination dataset...")
    if dry_run:
        print(f"[dry-run] Would delete {len(dest_docs)} documents from {dest_dataset_name}")
        return

    # Delete in batches of 50
    chunk_size = 50
    ops_client = dataset_client.transport.operations_client

    for i in range(0, len(dest_docs), chunk_size):
        chunk = dest_docs[i : i + chunk_size]
        doc_ids = [d.document_id for d in chunk]
        del_req = docai.BatchDeleteDocumentsRequest(
            dataset=dest_dataset_name,
            dataset_documents=docai.BatchDatasetDocuments(
                individual_document_ids=docai.BatchDatasetDocuments.IndividualDocumentIds(document_ids=doc_ids)
            ),
        )
        op = dataset_client.batch_delete_documents(request=del_req)
        op_name = op.operation.name

        # Safe poll to avoid Google Python SDK proto unpacking bug
        max_wait = 300
        poll_start = time.time()
        while time.time() - poll_start < max_wait:
            raw_op = ops_client.get_operation(op_name)
            if raw_op.done:
                if raw_op.error and raw_op.error.code != 0:
                    raise RuntimeError(f"Batch delete failed: {raw_op.error.message}")
                break
            time.sleep(3)

    log_pass("Existing destination dataset documents cleared.")


def restore_processor_from_gcs(
    dataset_client: docai.DocumentServiceClient,
    storage_client: storage.Client,
    target_ref: ProcessorRef,
    gcs_uri_prefix: str,
    allow_dataset_purge: bool,
    dry_run: bool,
) -> None:
    """Restores dataset_schema.json and split-categorized documents from a GCS snapshot."""
    clean_bucket, prefix = parse_gcs_uri(gcs_uri_prefix)
    if not prefix:
        raise ValueError(
            f"--restore-from-gcs requires a snapshot prefix (e.g. gs://{clean_bucket}/snapshots/<proc>/<timestamp>)"
        )
    bucket = storage_client.bucket(clean_bucket)
    target_dataset_name = f"{target_ref.name}/dataset"
    target_schema_name = dataset_client.dataset_schema_path(
        target_ref.project, target_ref.location, target_ref.processor_id
    )

    log_check(f"Restoring processor {target_ref.name} from snapshot gs://{clean_bucket}/{prefix}/...")
    ensure_destination_dataset_initialized(dataset_client, target_dataset_name, dry_run)

    # 1. Restore schema if present in snapshot
    schema_blob = bucket.blob(f"{prefix}/dataset_schema.json")
    if schema_blob.exists():
        raw_schema = schema_blob.download_as_text(encoding="utf-8")
        restored_schema = normalize_document_schema(
            docai.DocumentSchema.from_json(raw_schema, ignore_unknown_fields=True)
        )
        if dry_run:
            print(f"[dry-run] Would restore dataset_schema.json to {target_schema_name}")
        else:
            dataset_client.update_dataset_schema(
                dataset_schema=docai.DatasetSchema(name=target_schema_name, document_schema=restored_schema),
                update_mask=field_mask_pb2.FieldMask(paths=["document_schema"]),
            )
            log_pass(f"Restored dataset schema from gs://{clean_bucket}/{prefix}/dataset_schema.json")
    else:
        log_info(f"No dataset_schema.json found at gs://{clean_bucket}/{prefix}/; keeping current schema.")

    # 2. Discover documents per split in the snapshot
    split_counts: dict[str, int] = {}
    for split_key in _SPLIT_NAMES:
        blobs = list(storage_client.list_blobs(clean_bucket, prefix=f"{prefix}/{split_key}/"))
        json_blobs = [b for b in blobs if b.name.endswith(".json")]
        split_counts[split_key] = len(json_blobs)

    total_to_restore = sum(split_counts.values())
    log_info(f"Found {total_to_restore} document(s) in snapshot across splits: {split_counts}")

    # Back up and purge current documents before restoring
    backup_and_purge_destination_dataset(
        dataset_client=dataset_client,
        storage_client=storage_client,
        dest_dataset_name=target_dataset_name,
        dest_bucket_name=clean_bucket,
        dest_processor_id=target_ref.processor_id,
        dry_run=dry_run,
        dest_ref=target_ref,
        allow_dataset_purge=allow_dataset_purge,
    )

    if dry_run or total_to_restore == 0:
        if dry_run:
            print(f"[dry-run] Would import {split_counts} from gs://{clean_bucket}/{prefix}/ to {target_dataset_name}")
        return

    split_enum_map = {
        "DATASET_SPLIT_TRAIN": docai.DatasetSplitType.DATASET_SPLIT_TRAIN,
        "DATASET_SPLIT_TEST": docai.DatasetSplitType.DATASET_SPLIT_TEST,
        "DATASET_SPLIT_UNASSIGNED": docai.DatasetSplitType.DATASET_SPLIT_UNASSIGNED,
    }
    import_configs = [
        docai.ImportDocumentsRequest.BatchDocumentsImportConfig(
            batch_input_config=docai.BatchDocumentsInputConfig(
                gcs_prefix=docai.GcsPrefix(gcs_uri_prefix=f"gs://{clean_bucket}/{prefix}/{split_key}/")
            ),
            dataset_split=split_enum_map[split_key],
        )
        for split_key, count in split_counts.items()
        if count > 0
    ]

    op = dataset_client.import_documents(
        request=docai.ImportDocumentsRequest(
            dataset=target_dataset_name,
            batch_documents_import_configs=import_configs,
        )
    )
    op_name = op.operation.name
    ops_client = dataset_client.transport.operations_client
    max_wait = 1800
    poll_start = time.time()
    while time.time() - poll_start < max_wait:
        raw_op = ops_client.get_operation(op_name)
        if raw_op.done:
            if raw_op.error and raw_op.error.code != 0:
                raise RuntimeError(f"Snapshot restore import failed: {raw_op.error.message}")
            break
        time.sleep(10)
    else:
        raise TimeoutError(f"Snapshot restore timed out after {max_wait}s (operation {op_name})")

    log_pass(f"Successfully restored {total_to_restore} document(s) and schema from gs://{clean_bucket}/{prefix}/!")


def copy_dataset_data(
    dataset_client: docai.DocumentServiceClient,
    src: ProcessorRef,
    dest_ref: ProcessorRef,
    dest_bucket_name: str,
    dest_project_id: str,
    dry_run: bool,
    allow_dataset_purge: bool = True,
) -> None:
    src_dataset_name = f"{src.name}/dataset"
    dest_dataset_name = f"{dest_ref.name}/dataset"

    storage_client = storage.Client(
        project=dest_ref.project,
        client_options=ClientOptions(quota_project_id=dest_project_id),
    )
    clean_dest_bucket, _ = parse_gcs_uri(dest_bucket_name)
    d_bucket = storage_client.bucket(clean_dest_bucket)

    # The destination purge runs only AFTER the source has been listed and exported
    # to staging. If the source can't be read or the export fails, the destination
    # is left untouched.
    def purge_destination():
        backup_and_purge_destination_dataset(
            dataset_client=dataset_client,
            storage_client=storage_client,
            dest_dataset_name=dest_dataset_name,
            dest_bucket_name=dest_bucket_name,
            dest_processor_id=dest_ref.processor_id,
            dry_run=dry_run,
            dest_ref=dest_ref,
            allow_dataset_purge=allow_dataset_purge,
        )

    try:
        list_req = docai.ListDocumentsRequest(dataset=src_dataset_name, page_size=100, return_total_size=True)
        doc_list = list(dataset_client.list_documents(request=list_req))
    except NotFound as e:
        # Source genuinely has no dataset: purge the destination so it matches the source.
        log_info(f"Source processor has no dataset ({e}). Clearing destination to match; skipping document sync.")
        purge_destination()
        return
    except GoogleAPICallError as e:
        # Any other API error (e.g. PermissionDenied) means we could not read the source.
        # Stop rather than report a successful sync with no documents copied.
        raise RuntimeError(f"Could not list source dataset documents for {src.name}: {e}") from e

    if not doc_list:
        # Source dataset is empty: purge the destination so it matches the source.
        log_info("Source dataset has 0 documents. Clearing destination to match; skipping document sync.")
        purge_destination()
        return

    # Stage each run in its own prefix so reruns never import stale copies or documents
    # that have since been deleted from the source.
    run_timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    target_prefix = f"migrated-dataset-{src.processor_id}-{run_timestamp}"
    log_info(f"Exporting {len(doc_list)} documents categorized by their exact split from source...")
    log_info(f"Staging export to gs://{clean_dest_bucket}/{target_prefix}/")

    split_counts = {"DATASET_SPLIT_TRAIN": 0, "DATASET_SPLIT_TEST": 0, "DATASET_SPLIT_UNASSIGNED": 0}
    failed_exports: list[str] = []

    for idx, doc_meta in enumerate(doc_list):
        doc_id = doc_meta.document_id
        if hasattr(doc_meta, "dataset_type") and doc_meta.dataset_type:
            split_enum = doc_meta.dataset_type
            if split_enum == docai.DatasetSplitType.DATASET_SPLIT_TRAIN:
                split_name = "DATASET_SPLIT_TRAIN"
            elif split_enum == docai.DatasetSplitType.DATASET_SPLIT_TEST:
                split_name = "DATASET_SPLIT_TEST"
            else:
                split_name = "DATASET_SPLIT_UNASSIGNED"
        else:
            split_name = "DATASET_SPLIT_UNASSIGNED"

        doc_name_str = getattr(doc_id.unmanaged_doc_id, "doc_id", None) or f"doc_{idx}"
        file_path = f"{target_prefix}/{split_name}/{doc_name_str}.json"

        if not dry_run:
            blob = d_bucket.blob(file_path)

            def _export_one(doc_id=doc_id, blob=blob):
                get_doc_req = docai.GetDocumentRequest(dataset=src_dataset_name, document_id=doc_id)
                doc_response = dataset_client.get_document(request=get_doc_req)
                doc_json = docai.Document.to_json(doc_response.document)
                blob.upload_from_string(doc_json, content_type="application/json")

            try:
                with_retries(_export_one, label=f"export of document {doc_name_str}")
            except Exception as ex:
                log_fail(f"Failed exporting {doc_name_str} after retries: {ex}")
                failed_exports.append(doc_name_str)
                continue

        # Only count documents that were actually staged, so import batches match GCS.
        split_counts[split_name] += 1

    log_pass(f"Source dataset breakdown (exported): {split_counts}")

    if failed_exports:
        if len(failed_exports) == len(doc_list):
            # Nothing was staged, so purging the destination would leave it empty with
            # nothing to import. Stop here and leave the destination untouched.
            raise RuntimeError(
                f"All {len(doc_list)} source documents failed to export. "
                "Aborting before purge; destination dataset was not modified."
            )
        log_deferred_error(
            f"{len(failed_exports)} of {len(doc_list)} source documents failed to export and were "
            f"not imported: {failed_exports}"
        )

    # Source is now safely staged in GCS. Back up and purge the destination before importing.
    purge_destination()

    if dry_run:
        print(f"[dry-run] Would import preserved splits from gs://{clean_dest_bucket}/{target_prefix}/ to {dest_dataset_name}")
        return

    split_enum_map = {
        "DATASET_SPLIT_TRAIN": docai.DatasetSplitType.DATASET_SPLIT_TRAIN,
        "DATASET_SPLIT_TEST": docai.DatasetSplitType.DATASET_SPLIT_TEST,
        "DATASET_SPLIT_UNASSIGNED": docai.DatasetSplitType.DATASET_SPLIT_UNASSIGNED,
    }

    import_configs = []
    for split_key, count in split_counts.items():
        if count > 0:
            import_configs.append(
                docai.ImportDocumentsRequest.BatchDocumentsImportConfig(
                    batch_input_config=docai.BatchDocumentsInputConfig(
                        gcs_prefix=docai.GcsPrefix(
                            gcs_uri_prefix=f"gs://{clean_dest_bucket}/{target_prefix}/{split_key}/"
                        )
                    ),
                    dataset_split=split_enum_map[split_key],
                )
            )

    if import_configs:
        print(f"Triggering Document AI import preserving exact splits ({len(import_configs)} split batches)...")
        # Dataset import problems do not stop the migration: model versions can still be
        # imported, deployed, and set as default independently. But a real failure is
        # recorded so the run ends with exit code 3 instead of reporting success.
        # A local polling timeout is only a warning, since the operation keeps running on GCP.
        op_name = None
        try:
            import_req = docai.ImportDocumentsRequest(
                dataset=dest_dataset_name,
                batch_documents_import_configs=import_configs,
            )
            op = dataset_client.import_documents(request=import_req)
            print("  Import LRO running. Waiting for completion...")

            # Safe poll avoiding SDK Empty -> ImportDocumentsResponse deserialization bug
            op_name = op.operation.name
            ops_client = dataset_client.transport.operations_client
            max_wait = 1800  # 30 minutes for large datasets
            poll_start = time.time()

            while time.time() - poll_start < max_wait:
                raw_op = ops_client.get_operation(op_name)
                if raw_op.done:
                    if raw_op.error and raw_op.error.code != 0:
                        log_deferred_error(
                            f"Dataset import failed (operation {op_name}): {raw_op.error.message}"
                        )
                        return
                    break
                time.sleep(10)
            else:
                print(
                    f"  {YELLOW}[WARNING]{RESET} Import still running after {max_wait // 60} minutes. "
                    f"It continues in the background on GCP. Check status of operation: {op_name}"
                )
                return

            log_pass("Documents successfully imported into destination preserving exact source train/test/unassigned splits!")
        except Exception as e:
            op_ref = f" (operation {op_name})" if op_name else ""
            log_deferred_error(f"Dataset import failed{op_ref}: {e}")


def select_source_versions(
    src_client: docai.DocumentProcessorServiceClient,
    src: ProcessorRef,
    mode: str,
    version_id: Optional[str],
):
    source_processor = src_client.get_processor(name=src.name)
    all_versions = list(src_client.list_processor_versions(parent=src.name))
    # Key by short version ID: the API returns resource names with the project *number*
    # (projects/1234/...), so comparing against names built from the project ID would miss.
    by_id = {v.name.split("/")[-1]: v for v in all_versions}

    if mode == "specific":
        short_id = version_id.split("/")[-1]
        if short_id not in by_id:
            raise ValueError(f"Version {version_id!r} not found. Available: {sorted(by_id)}")
        chosen = [by_id[short_id]]
    elif mode == "default":
        default_name = source_processor.default_processor_version
        default_id = default_name.split("/")[-1] if default_name else ""
        if not default_id or default_id not in by_id:
            raise ValueError("No resolvable default version; specify --version-id or --versions all.")
        chosen = [by_id[default_id]]
    elif mode == "all":
        chosen = all_versions
    else:
        raise ValueError(f"Unknown mode: {mode}")

    importable, foundation, pretrained = [], [], []
    for v in chosen:
        if v.google_managed:
            # Zero-shot processors have no custom version: the "model" is the pinned pretrained
            # version. The same pretrained IDs exist in every processor of the same type, so it
            # is promoted by pinning the destination default to the same ID (no import needed).
            if mode in ("specific", "default") or v.name == source_processor.default_processor_version:
                log_info(
                    f"Pinned Google pretrained version '{v.name.split('/')[-1]}' selected: "
                    "will be set as destination default by ID (no import needed)."
                )
                pretrained.append(v)
            else:
                log_info(f"Skipping '{v.name.split('/')[-1]}': Google-managed pretrained version (not the source default).")
            continue
        if is_versioned_foundation(v):
            log_info(f"Found Pinned Google Foundation model '{v.display_name}'. Schema will be copied.")
            foundation.append(v)
            continue
        if v.state not in _IMPORTABLE_STATES:
            log_info(f"Skipping '{v.display_name}': state is {docai.ProcessorVersion.State(v.state).name}.")
            continue
        importable.append(v)

    return importable, foundation, pretrained, source_processor


def ensure_destination_processor(
    dst_client: docai.DocumentProcessorServiceClient,
    dest_project: str,
    dest_location: str,
    processor_type: str,
    display_name: str,
    existing_dest_processor: Optional[str],
    dry_run: bool,
) -> str:
    if existing_dest_processor:
        ref = parse_processor(existing_dest_processor, default_project=dest_project, default_location=dest_location)
        try:
            proc = dst_client.get_processor(name=ref.name)
            if proc.type_ != processor_type:
                raise ValueError(
                    f"Destination processor type {proc.type_!r} does not match source {processor_type!r}."
                )
            log_info(f"Reusing specified destination processor: {ref.name}")
            return ref.name
        except NotFound:
            log_info(f"Specified destination processor '{ref.name}' does not exist yet. It will be created.")

    parent = f"projects/{dest_project}/locations/{dest_location}"
    try:
        existing = dst_client.list_processors(parent=parent)
        for p in existing:
            if p.display_name == display_name and p.type_ == processor_type:
                log_info(f"Reusing existing destination processor: {p.name}")
                return p.name
    except Exception:
        pass

    if dry_run:
        return f"{parent}/processors/<new-id>"

    created = dst_client.create_processor(
        parent=parent,
        processor=docai.Processor(type_=processor_type, display_name=display_name),
    )
    log_pass(f"Created destination processor: {created.name}")
    return created.name


class VersionMap:
    """Memory of which destination version was imported from which source version.

    Why: ImportProcessorVersion gives the imported version a NEW id in the destination and
    keeps only the display name; the API records no provenance. Matching by display name is
    therefore a heuristic that breaks as soon as two source versions share a name (e.g. a
    re-trained 'custom-v1'). This map is the authoritative record instead.

    Storage: one JSON object per destination processor at
        <root>/<destination_processor_id>.json
    where <root> is a gs://bucket/prefix (recommended: the Terraform state bucket, prefix
    "<env>/version_map") or a local directory for laptop runs. Git stays the statement of
    intent (manifests), BigQuery stays the audit log; this file is the runtime memory.

    Layout:
        {"schema_version": 1,
         "destination_processor": "projects/<n>/locations/us/processors/<id>",
         "source_processor":      "projects/<n>/locations/us/processors/<id>",
         "versions": {"<source_version_id>": {"destination_version": "<full name>",
                                              "display_name": "...", "action": "imported|adopted",
                                              "recorded_at": "<iso8601>"}}}
    """

    def __init__(self, root: str, dest_processor_name: str, source_processor_name: str, quota_project: str):
        self.root = root.rstrip("/")
        self.dest_processor_name = dest_processor_name
        self.source_processor_name = source_processor_name
        self.dest_processor_id = dest_processor_name.split("/")[-1]
        self._blob = None
        self._path: Optional[Path] = None
        if self.root.startswith("gs://"):
            bucket_name, _, prefix = self.root[5:].partition("/")
            st = storage.Client(project=quota_project, client_options=ClientOptions(quota_project_id=quota_project))
            object_name = f"{prefix}/{self.dest_processor_id}.json" if prefix else f"{self.dest_processor_id}.json"
            self._blob = st.bucket(bucket_name).blob(object_name)
            self.uri = f"gs://{bucket_name}/{object_name}"
        else:
            self._path = Path(self.root) / f"{self.dest_processor_id}.json"
            self.uri = str(self._path)
        self.data = self._load()

    # -- persistence -------------------------------------------------------------------------
    def _load(self) -> dict:
        raw = None
        if self._blob is not None:
            if self._blob.exists():
                raw = self._blob.download_as_text()
        elif self._path is not None and self._path.exists():
            raw = self._path.read_text()
        if raw:
            data = json.loads(raw)
            data.setdefault("versions", {})
            return data
        return {
            "schema_version": 1,
            "destination_processor": self.dest_processor_name,
            "source_processor": self.source_processor_name,
            "versions": {},
        }

    def save(self) -> None:
        body = json.dumps(self.data, indent=2, sort_keys=True) + "\n"
        if self._blob is not None:
            self._blob.upload_from_string(body, content_type="application/json")
        else:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(body)

    # -- queries -----------------------------------------------------------------------------
    @property
    def is_empty(self) -> bool:
        return not self.data["versions"]

    def lookup(self, source_version_id: str) -> Optional[str]:
        entry = self.data["versions"].get(source_version_id)
        return entry.get("destination_version") if entry else None

    def source_for(self, dest_version_name: str) -> Optional[str]:
        """Reverse lookup: which source version id (if any) produced this destination version."""
        dest_id = dest_version_name.split("/")[-1]
        for sid, entry in self.data["versions"].items():
            if entry.get("destination_version", "").split("/")[-1] == dest_id:
                return sid
        return None

    def record(self, source_version_id: str, dest_version_name: str, display_name: str, action: str) -> None:
        self.data["versions"][source_version_id] = {
            "destination_version": dest_version_name,
            "display_name": display_name,
            "action": action,
            "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        }
        self.save()

    def forget(self, source_version_id: str) -> None:
        if self.data["versions"].pop(source_version_id, None) is not None:
            self.save()


def import_version(
    dst_client: docai.DocumentProcessorServiceClient,
    dest_processor_name: str,
    source_version: docai.ProcessorVersion,
    source_location: str,
    dry_run: bool,
    import_timeout_seconds: int = 2400,
    version_map: Optional[VersionMap] = None,
    lineage: Optional[dict] = None,
) -> Optional[str]:
    """Returns the destination version name for source_version, importing it if needed.

    Resolution order (see VersionMap for why display names are not trusted):
      1. version map hit  -> reuse that exact destination version (if it still exists and is
                             not FAILED; a stale entry is dropped and the import is redone).
      2. no map entry     -> look for a destination version with the same display name:
           - none                         -> import.
           - exists, not claimed by another source version in the map
                                          -> ADOPT it (destination predates the map); recorded.
           - exists, mapped to a DIFFERENT source version -> name collision: import anyway,
                                          both versions coexist, the new one is recorded.
      3. no --version-map configured -> legacy behaviour: reuse by display name, with a warning.
    `lineage` (optional dict) receives source_version_id/destination_version_id/action for the run log.
    """
    src_ver_id = source_version.name.split("/")[-1]
    label = source_version.display_name or src_ver_id
    lineage = lineage if lineage is not None else {}
    lineage["source_version_id"] = src_ver_id

    def _done(dest_name: str, action: str) -> str:
        lineage["destination_version_id"] = dest_name.split("/")[-1]
        lineage["version_action"] = action
        return dest_name

    # 1. authoritative memory
    if version_map is not None:
        mapped = version_map.lookup(src_ver_id)
        if mapped:
            try:
                mv = dst_client.get_processor_version(name=mapped)
                if mv.state != docai.ProcessorVersion.State.FAILED:
                    log_pass(
                        f"Version map: source {src_ver_id} ('{label}') -> destination {mapped.split('/')[-1]} "
                        f"(state={docai.ProcessorVersion.State(mv.state).name}). Reusing, no import."
                    )
                    return _done(mapped, "reused")
                print(f"  {YELLOW}[WARNING]{RESET} Version map points {src_ver_id} at {mapped.split('/')[-1]}, which is FAILED. Re-importing.")
            except NotFound:
                print(f"  {YELLOW}[WARNING]{RESET} Version map points {src_ver_id} at {mapped.split('/')[-1]}, which no longer exists. Re-importing.")
            if not dry_run:
                version_map.forget(src_ver_id)

    # 2./3. display-name lookup (adoption or legacy heuristic)
    if dest_processor_name.endswith("/processors/<new-id>"):
        # Dry run against a destination processor that does not exist yet (would be created):
        # there are no versions to match and the placeholder must not reach the API.
        print("[dry-run] Destination processor does not exist yet; no existing versions to match.")
        existing_dest_versions = []
    else:
        existing_dest_versions = list(dst_client.list_processor_versions(parent=dest_processor_name))
    same_name = [
        ev for ev in existing_dest_versions
        if ev.state != docai.ProcessorVersion.State.FAILED and ev.display_name == source_version.display_name
    ]
    if same_name:
        ev = same_name[0]
        ev_id = ev.name.split("/")[-1]
        state_name = docai.ProcessorVersion.State(ev.state).name
        if version_map is None:
            print(
                f"  {YELLOW}[WARNING]{RESET} No --version-map configured: reusing destination version '{ev.display_name}' "
                f"({ev_id}, state={state_name}) by display name only. If source {src_ver_id} is a different "
                f"model with the same name this is WRONG; configure --version-map to pin by id."
            )
            return _done(ev.name, "reused_by_name")
        claimed_by = version_map.source_for(ev.name)
        if claimed_by is None:
            # Destination predates the map (or was created by hand): adopt once, then it is pinned.
            print(
                f"  {YELLOW}[WARNING]{RESET} Adopting destination version '{ev.display_name}' ({ev_id}, state={state_name}) "
                f"as the import of source {src_ver_id}: it is not yet in the version map and nothing else claims it. "
                f"Verify once; from now on it is pinned by id in {version_map.uri}."
            )
            if not dry_run:
                version_map.record(src_ver_id, ev.name, ev.display_name, "adopted")
            return _done(ev.name, "adopted")
        print(
            f"  {YELLOW}[WARNING]{RESET} Display-name collision: destination already has '{ev.display_name}' ({ev_id}) "
            f"but it was imported from source version {claimed_by}, not {src_ver_id}. Importing {src_ver_id} as a "
            f"separate version; both will coexist with the same name and the default moves to the new one."
        )

    req = docai.ImportProcessorVersionRequest(
        parent=dest_processor_name,
        external_processor_version_source=docai.ImportProcessorVersionRequest.ExternalProcessorVersionSource(
            processor_version=source_version.name,
            service_endpoint=f"https://{docai_endpoint(source_location)}",
        ),
    )

    if dry_run:
        print(f"[dry-run] Would import version {label!r} (source ID: {src_ver_id})")
        return None

    print(f"\nImporting version '{label}' (source ID: {src_ver_id}, timeout: {import_timeout_seconds // 60}m)...")
    t0 = time.monotonic()
    op = dst_client.import_processor_version(request=req)
    res = op.result(timeout=import_timeout_seconds)
    new_name = getattr(res, "processor_version", "") or ""
    log_pass(f"Imported version as: {new_name} (import took {_elapsed(t0)})")
    if new_name and version_map is not None:
        # Record immediately, before deploy: a failed deploy must not cause a second import.
        version_map.record(src_ver_id, new_name, source_version.display_name or "", "imported")
        log_info(f"Version map updated: {src_ver_id} -> {new_name.split('/')[-1]} ({version_map.uri})")
    return _done(new_name, "imported") if new_name else None


def wait_until_deployed(
    dst_client: docai.DocumentProcessorServiceClient,
    version_name: str,
    max_wait_seconds: int = 1800,
    poll_interval: int = 15,
) -> bool:
    start_time = time.time()
    print(f"Waiting for version {version_name.split('/')[-1]} to finish deploying...")
    while time.time() - start_time < max_wait_seconds:
        try:
            v = dst_client.get_processor_version(name=version_name)
            if v.state == docai.ProcessorVersion.State.DEPLOYED:
                log_pass(f"Version {version_name.split('/')[-1]} is fully DEPLOYED (waited {int(time.time() - start_time)}s).")
                return True
            elif v.state == docai.ProcessorVersion.State.FAILED:
                log_fail(f"Version {version_name.split('/')[-1]} deployment failed in Google Cloud.")
                return False
            time.sleep(poll_interval)
        except Exception:
            time.sleep(poll_interval)
    log_fail(f"Timed out waiting for {version_name.split('/')[-1]} to deploy.")
    return False


def _raise_if_deploy_error_is_fatal(e: Exception, version_name: str) -> None:
    """Fail fast on deploy errors that polling can never recover from.

    The deploy call is wrapped in a try/except because a concurrent or prior deploy can
    surface as ALREADY_EXISTS / FAILED_PRECONDITION / ABORTED while the version is really
    DEPLOYING; those are safe to poll. Billing, permission and argument errors are not:
    the version will stay UNDEPLOYED forever, so raise immediately with the API message.
    """
    if isinstance(e, (gexc.PermissionDenied, gexc.InvalidArgument, gexc.NotFound, gexc.Unauthenticated)):
        raise RuntimeError(
            f"Deploy of {version_name.split('/')[-1]} rejected by Document AI "
            f"({type(e).__name__}): {getattr(e, 'message', str(e)).splitlines()[0]}"
        ) from e


def deploy_and_default(
    dst_client: docai.DocumentProcessorServiceClient,
    dest_processor_name: str,
    version_name: str,
    deploy: bool,
    set_default: bool,
    dry_run: bool,
) -> None:
    if not version_name or dry_run:
        return

    v_info = dst_client.get_processor_version(name=version_name)
    is_deployed = v_info.state == docai.ProcessorVersion.State.DEPLOYED

    if deploy and not is_deployed:
        print(f"Deploying {version_name.split('/')[-1]}...")
        t_deploy = time.monotonic()
        try:
            op = dst_client.deploy_processor_version(name=version_name)
            op.result(timeout=1800)
            is_deployed = True
            log_pass(f"Version {version_name.split('/')[-1]} deployed (deploy took {_elapsed(t_deploy)}).")
        except Exception as e:
            _raise_if_deploy_error_is_fatal(e, version_name)
            log_info(f"Deploy notification: {e}")
            is_deployed = wait_until_deployed(dst_client, version_name)

    if set_default:
        # A version must be DEPLOYED before it can be set as default. If deployment was
        # not requested and the version is neither deployed nor already deploying, it will
        # never reach DEPLOYED, so fail immediately instead of polling until timeout.
        if (
            not is_deployed
            and not deploy
            and v_info.state != docai.ProcessorVersion.State.DEPLOYING
        ):
            raise RuntimeError(
                f"Cannot set {version_name} as default: it is not deployed and --deploy was not set. "
                "Re-run with --deploy (deploy_version = true) or disable --set-default."
            )

        if not is_deployed:
            is_deployed = wait_until_deployed(dst_client, version_name)

        if not is_deployed:
            raise RuntimeError(
                f"Cannot set {version_name} as default because it is not in DEPLOYED state."
            )

        print(f"Setting default version to {version_name}...")
        dst_client.set_default_processor_version(
            request=docai.SetDefaultProcessorVersionRequest(
                processor=dest_processor_name,
                default_processor_version=version_name,
            )
        ).result()
        log_pass("Default version set.")


# ---------------------------------------------------------------------------
# Step 7 - verify the copy. Read-only: reads the copy back and compares it with the source,
# the same eight checks `compare_processors.py --migration` prints. It runs BEFORE step 8 makes
# the version the default: a version can be called by its ID, so production keeps serving its
# current default while the copy is checked. A failed check is an error of the run (exit 3), so the
# Terraform apply (and the CI run) goes red instead of green, and the default is not switched.
# ---------------------------------------------------------------------------


def _schema_field_index(doc_schema: docai.DocumentSchema) -> dict[tuple[str, str], tuple]:
    """(entity type, field) -> (value type, occurrence, method, description, inactive), in schema order."""
    out: dict[tuple[str, str], tuple] = {}
    for et in doc_schema.entity_types:
        for p in et.properties:
            out[(et.name, p.name)] = (
                p.value_type,
                p.occurrence_type.name if p.occurrence_type else "",
                p.method.name if p.method else "",
                p.description or "",
                bool(p.property_metadata.inactive) if p.property_metadata else False,
            )
    return out


def _schema_difference(expected: docai.DocumentSchema, actual: docai.DocumentSchema, limit: int = 6) -> str:
    """Short human summary of how two schemas differ (field names only, never values)."""
    a, b = _schema_field_index(expected), _schema_field_index(actual)
    missing = [f"{et}/{f}" for (et, f) in a if (et, f) not in b]
    extra = [f"{et}/{f}" for (et, f) in b if (et, f) not in a]
    changed = [f"{et}/{f}" for (et, f) in a if (et, f) in b and a[(et, f)] != b[(et, f)]]
    parts = []
    if missing:
        parts.append(f"missing on the copy: {', '.join(missing[:limit])}{'…' if len(missing) > limit else ''}")
    if extra:
        parts.append(f"extra on the copy: {', '.join(extra[:limit])}{'…' if len(extra) > limit else ''}")
    if changed:
        parts.append(f"different type/occurrence/method/description: {', '.join(changed[:limit])}{'…' if len(changed) > limit else ''}")
    if not parts and list(a) != list(b):
        parts.append("same fields in a different order")
    return "; ".join(parts) or "schema display name, description or entity-type metadata differ"


def _field_count(doc_schema: docai.DocumentSchema) -> int:
    return sum(len(et.properties) for et in doc_schema.entity_types)


def _model_kind(v: docai.ProcessorVersion) -> str:
    """'FINE_TUNED on pretrained-foundation-model-v1.5-…', 'VERSIONED_FOUNDATION on …', or '-'."""
    gi = v.gen_ai_model_info
    if "custom_gen_ai_model_info" in gi:
        c = gi.custom_gen_ai_model_info
        return f"{c.custom_model_type.name} on {c.base_processor_version_id or '-'}"
    if "foundation_gen_ai_model_info" in gi:
        return "FOUNDATION (Google pretrained)"
    return "-"


def verify_copy(
    src_client: docai.DocumentProcessorServiceClient,
    dst_client: docai.DocumentProcessorServiceClient,
    dataset_client: docai.DocumentServiceClient,
    src: ProcessorRef,
    dest_ref: ProcessorRef,
    src_proc: docai.Processor,
    src_version_name: Optional[str],
    dst_version_name: Optional[str],
    expect_deployed: bool,
    expect_default: bool,
    schema_file: Optional[str],
) -> tuple[list[tuple[str, bool, str]], list[str]]:
    """Reads the copy back and compares it with the source. Returns (checks, infos);
    each check is (name, passed, detail). Nothing is created or changed."""
    checks: list[tuple[str, bool, str]] = []
    infos: list[str] = []

    dst_proc = dst_client.get_processor(name=dest_ref.name)
    checks.append(("processor type equal", dst_proc.type_ == src_proc.type_, f"source {src_proc.type_} / copy {dst_proc.type_}"))

    # 2. the copy's dataset schema must be the released schema: the Git file, else the source's live schema
    dst_schema = dataset_client.get_dataset_schema(
        name=dataset_client.dataset_schema_path(dest_ref.project, dest_ref.location, dest_ref.processor_id)
    ).document_schema
    dst_json = document_schema_to_canonical_json(dst_schema)
    src_schema = None
    try:
        src_ds_client = dataset_client_for(src.location, quota_project_id=dest_ref.project)
        src_schema = src_ds_client.get_dataset_schema(
            name=src_ds_client.dataset_schema_path(src.project, src.location, src.processor_id)
        ).document_schema
    except Exception as e:  # viewer on the source may be missing; the file is still the reference
        infos.append(f"could not read the source's live dataset schema ({type(e).__name__}); compared against the schema file only")
    if schema_file:
        expected, expected_label = load_schema_from_file(schema_file), "the Git schema file"
    elif src_schema is not None:
        expected, expected_label = src_schema, "the source's schema"
    else:
        expected, expected_label = None, "nothing readable"
    if expected is None:
        checks.append(("dataset schema identical", False, "neither a schema file nor the source schema could be read"))
    else:
        same = dst_json == document_schema_to_canonical_json(expected)
        checks.append((f"dataset schema identical to {expected_label} (fields, types, occurrence, method, descriptions, order)",
                       same, f"{_field_count(expected)} fields expected, {_field_count(dst_schema)} on the copy"
                       + ("" if same else f"; {_schema_difference(expected, dst_schema)}")))
        if schema_file and src_schema is not None and document_schema_to_canonical_json(src_schema) != document_schema_to_canonical_json(expected):
            infos.append("the source's live schema no longer matches the Git schema file (edited after the export); "
                         "the copy follows the file - re-export if the change is wanted")

    # 3-8. the version
    if not dst_version_name:
        infos.append("no version was selected in this run, so the version checks are skipped")
        return checks, infos
    dst_vid = dst_version_name.split("/")[-1]
    src_vid = (src_version_name or "").split("/")[-1]
    dst_v = dst_client.get_processor_version(name=dst_version_name)
    src_v = None
    if src_version_name:
        try:
            src_v = src_client.get_processor_version(name=src_version_name)
        except NotFound:
            src_v = None
    checks.append((f"source version {src_vid or '?'} exists on the source", src_v is not None,
                   f"'{src_v.display_name}' state {src_v.state.name}" if src_v else "not found on the source"))
    deployed = dst_v.state == docai.ProcessorVersion.State.DEPLOYED
    current_default = (dst_proc.default_processor_version or "").split("/")[-1] or "-"
    if expect_deployed and expect_default:
        checks.append((f"copy's default version is {dst_vid} and deployed", deployed and current_default == dst_vid,
                       f"state {dst_v.state.name}, default is {current_default}"))
    elif expect_deployed:
        checks.append((f"copy's version {dst_vid} is deployed", deployed, f"state {dst_v.state.name}"))
    elif expect_default:
        checks.append((f"copy's default version is {dst_vid}", current_default == dst_vid, f"default is {current_default}"))
    if src_vid.startswith("pretrained-"):
        checks.append(("same pretrained version pinned on the copy", dst_vid == src_vid, f"copy pinned to {dst_vid}"))
        return checks, infos
    if src_v is None:
        return checks, infos
    checks.append(("copy's version has the source version's name", dst_v.display_name == src_v.display_name,
                   f"source '{src_v.display_name}' / copy '{dst_v.display_name}'"))
    checks.append(("a real copy, not Google's pretrained model", (not dst_v.google_managed) and dst_v.model_type == src_v.model_type,
                   f"copy modelType {dst_v.model_type.name}, googleManaged {bool(dst_v.google_managed)}"))
    ks, kd = _model_kind(src_v), _model_kind(dst_v)
    checks.append(("same kind and base model", ks == kd, f"source {ks} / copy {kd}"))
    # the version carries the schema it was created with - that is what inference uses
    sv_json, dv_json = document_schema_to_canonical_json(src_v.document_schema), document_schema_to_canonical_json(dst_v.document_schema)
    n_sv, n_dv = _field_count(src_v.document_schema), _field_count(dst_v.document_schema)
    checks.append(("version's own schema identical (what inference uses)", sv_json == dv_json and n_sv > 0,
                   f"{n_sv} fields in the source version, {n_dv} in the copy's"
                   + ("" if sv_json == dv_json else f"; {_schema_difference(src_v.document_schema, dst_v.document_schema)}")))
    if n_dv and dv_json != dst_json:
        infos.append("the copy's dataset schema differs from the schema inside its version (the released schema was edited "
                     "after the version was created); inference uses the version's own schema")
    return checks, infos


def print_verification(checks: list[tuple[str, bool, str]], infos: list[str]) -> list[str]:
    """Prints the PASS/FAIL block; returns the names of the failed checks."""
    print(f"\n{BOLD}7. Verify the copy before it becomes the default (read back and compared with the source){RESET}")
    for name, ok, detail in checks:
        print(f"  {GREEN if ok else RED}[{'PASS' if ok else 'FAIL'}]{RESET} {name}  - {detail}")
    for line in infos:
        print(f"  info: {line}")
    failed = [name for name, ok, _ in checks if not ok]
    if failed:
        print(f"  {RED}{BOLD}VERIFY RESULT: {len(failed)} of {len(checks)} checks FAILED{RESET}")
    else:
        print(f"  {GREEN}{BOLD}VERIFY RESULT: all {len(checks)} checks passed{RESET}")
    return failed


# ---------------------------------------------------------------------------
# Step 8 - make the verified version the default. The version was deployed in step 6 and checked
# in step 7 while the processor kept serving its current default. Switch only when every check
# passed (verified is True) or verification was turned off with --no-verify (verified is None);
# after a failed or incomplete verification (verified is False) the default is left alone, so
# production never serves an unverified copy. After switching, the processor is read back to
# confirm the switch took effect.
# ---------------------------------------------------------------------------


def switch_default_after_verification(
    dst_client: docai.DocumentProcessorServiceClient,
    dest_processor_name: str,
    version_name: Optional[str],
    *,
    deploy: bool,
    set_default: bool,
    verified: Optional[bool],
    dry_run: bool,
    run_row: dict,
) -> Optional[str]:
    """Returns a description of a failed switch confirmation, or None (switched, skipped or not wanted)."""
    if not version_name or not set_default:
        return None
    vid = version_name.split("/")[-1]
    if dry_run:
        print(f"[dry-run] Would set {vid} as the default version once every check has passed")
        return None
    print(f"\n{BOLD}8. Set as default{RESET}")
    if verified is False:
        current = (dst_client.get_processor(name=dest_processor_name).default_processor_version or "").split("/")[-1]
        print(f"  info: not switched - verification did not pass; the processor keeps its current default ({current or 'none'})")
        run_row["default_processor_version"] = current or None
        return None
    deploy_and_default(dst_client, dest_processor_name, version_name, deploy, True, False)
    run_row["default_processor_version"] = vid
    now = (dst_client.get_processor(name=dest_processor_name).default_processor_version or "").split("/")[-1]
    ok = now == vid
    print(f"  {GREEN if ok else RED}[{'PASS' if ok else 'FAIL'}]{RESET} copy's default version is {vid}  - default is {now or 'none'}")
    return None if ok else f"the default version is {now or 'none'}, expected {vid}"


# ---------------------------------------------------------------------------
# BigQuery run logging (client request): one row per script run.
# ---------------------------------------------------------------------------

STATUS_SUCCESS = "SUCCESS"                               # exit 0
STATUS_COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"   # exit 3
STATUS_FAILED = "FAILED"                                 # exit 1
STATUS_PREFLIGHT_FAILED = "PREFLIGHT_FAILED"             # exit 2

BQ_RUN_LOG_SCHEMA = [
    bigquery.SchemaField("execution_timestamp", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("source_project_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("source_processor_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("source_processor_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("destination_project_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("destination_processor_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("destination_processor_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("default_processor_version", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("dataset_copied", "BOOLEAN", mode="NULLABLE"),
    # Version lineage (added with --version-map): which source version became which destination
    # version in this run, and how it was resolved (imported | reused | adopted | reused_by_name).
    bigquery.SchemaField("source_version_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("destination_version_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("version_action", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("version_map_uri", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("execution_status", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("error_message", "STRING", mode="NULLABLE"),
    # Step 7: "PASS 8/8", "FAIL: <failed check names>", "ERROR: <why it could not run>" or "SKIPPED";
    # step 8 appends "; default switched", "; default unchanged" or "; FAIL: default not switched".
    bigquery.SchemaField("verification", "STRING", mode="NULLABLE"),
]

_BQ_ERROR_MESSAGE_MAX_LEN = 1000


def bigquery_location_for(docai_location: str) -> str:
    """Maps a Document AI location ('us', 'eu') to a BigQuery location ('US', 'EU')."""
    return {"us": "US", "eu": "EU"}.get(docai_location.lower(), docai_location)


def ensure_bigquery_table(
    client: bigquery.Client, dataset_id: str, table_id: str, location: str
) -> bigquery.TableReference:
    """Checks for the log dataset/table and creates them if missing.

    If the table already exists with an older schema, adds any missing columns and
    relaxes REQUIRED columns that this schema treats as NULLABLE (both are allowed
    in-place BigQuery schema changes).
    """
    dataset_ref = bigquery.DatasetReference(client.project, dataset_id)
    try:
        client.get_dataset(dataset_ref)
    except NotFound:
        log_info(f"Creating BigQuery dataset {client.project}.{dataset_id} in {location}...")
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = location
        client.create_dataset(dataset, exists_ok=True)

    table_ref = dataset_ref.table(table_id)
    try:
        table = client.get_table(table_ref)
    except NotFound:
        log_info(f"Creating BigQuery table {client.project}.{dataset_id}.{table_id}...")
        client.create_table(bigquery.Table(table_ref, schema=BQ_RUN_LOG_SCHEMA), exists_ok=True)
        return table_ref

    existing = {f.name: f for f in table.schema}
    new_schema, changed = [], False
    for f in table.schema:
        wanted = next((w for w in BQ_RUN_LOG_SCHEMA if w.name == f.name), None)
        if wanted is not None and f.mode == "REQUIRED" and wanted.mode == "NULLABLE":
            new_schema.append(bigquery.SchemaField(f.name, f.field_type, mode="NULLABLE"))
            changed = True
        else:
            new_schema.append(f)
    for w in BQ_RUN_LOG_SCHEMA:
        if w.name not in existing:
            new_schema.append(w)
            changed = True
    if changed:
        log_info(f"Updating schema of BigQuery table {client.project}.{dataset_id}.{table_id}...")
        table.schema = new_schema
        client.update_table(table, ["schema"])
    return table_ref


def log_run_to_bigquery(row: dict, project_id: str, dataset_id: str, table_id: str, location: str) -> None:
    """Writes one run-log row to BigQuery. Never raises: logging must not affect the migration result.

    Uses a load job rather than a streaming insert, because streaming inserts into a
    newly created table are often rejected for several minutes after creation.
    """
    try:
        client = bigquery.Client(project=project_id)
        table_ref = ensure_bigquery_table(client, dataset_id, table_id, location)
        job_config = bigquery.LoadJobConfig(
            schema=BQ_RUN_LOG_SCHEMA,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        client.load_table_from_json([row], table_ref, job_config=job_config).result(timeout=120)
        log_pass(f"Logged run to BigQuery table {project_id}.{dataset_id}.{table_id} (status: {row['execution_status']}).")
    except Exception as e:
        print(f"  {YELLOW}[WARNING]{RESET} Could not log this run to BigQuery ({e}). Migration result is unaffected.")


def _error_summary(*parts: Optional[str]) -> Optional[str]:
    """Joins non-empty messages and truncates to fit the error_message column."""
    text = " | ".join(p for p in parts if p)
    return text[:_BQ_ERROR_MESSAGE_MAX_LEN] if text else None


def apply_manifest_defaults(args: argparse.Namespace) -> None:
    """Populates CLI args from a YAML/JSON manifest file when --manifest is provided."""
    if not args.manifest:
        return
    m = load_manifest_file(args.manifest)
    if not args.source_processor and m.get("source_processor"):
        args.source_processor = str(m["source_processor"])
    if not args.dest_project and m.get("destination_project_id"):
        args.dest_project = str(m["destination_project_id"])
    if not args.dest_location and m.get("location"):
        args.dest_location = str(m["location"])
    if not args.dest_processor and m.get("destination_processor"):
        args.dest_processor = str(m["destination_processor"])
    if not args.dest_display_name and m.get("display_name"):
        args.dest_display_name = str(m["display_name"])
    if not args.version_id and m.get("source_version_id"):
        args.version_id = str(m["source_version_id"])
    if m.get("versions_mode") in ("default", "all") and args.versions == "default":
        args.versions = str(m["versions_mode"])
    if not args.schema_file and m.get("schema_file"):
        args.schema_file = str(m["schema_file"])
    if m.get("deploy") is True:
        args.deploy = True
    if m.get("set_default") is True:
        args.set_default = True
    if m.get("copy_dataset") is True:
        args.copy_dataset = True
    if not args.dest_dataset_bucket and m.get("destination_dataset_bucket"):
        args.dest_dataset_bucket = str(m["destination_dataset_bucket"])
    if m.get("allow_dataset_purge") is True:
        args.allow_dataset_purge = True


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Document AI Declarative Promotion, Schema Sync, and Dataset Snapshot/Restore Tool"
    )
    p.add_argument("--manifest", default=None, help="Path to a YAML/JSON processor manifest file")
    p.add_argument("--source-processor", default=None, help="Source processor full resource name")
    p.add_argument("--dest-project", default=None, help="Destination GCP project ID")
    p.add_argument("--dest-location", default=None, help="Destination region (e.g. 'us' or 'eu')")
    p.add_argument("--dest-processor", default=None, help="Destination processor resource name or ID (Optional)")
    p.add_argument("--dest-display-name", default=None)
    p.add_argument("--versions", choices=["default", "all"], default="default")
    p.add_argument("--version-id", default=None)
    p.add_argument("--deploy", action="store_true")
    p.add_argument("--set-default", action="store_true")
    p.add_argument("--copy-dataset", action="store_true")
    p.add_argument("--dest-dataset-bucket", default=None)
    p.add_argument(
        "--allow-dataset-purge",
        action="store_true",
        help="Allow purging an existing non-empty destination dataset after backing it up to GCS",
    )
    p.add_argument(
        "--schema-file",
        default=None,
        help="Path to a Git-tracked DocumentSchema JSON file to apply to the destination processor",
    )
    p.add_argument(
        "--export-schema",
        default=None,
        help="Export the processor's DocumentSchema to this JSON file path for Git tracking",
    )
    p.add_argument(
        "--snapshot-to-gcs",
        default=None,
        help="Take a non-destructive restorable snapshot (schema + split documents) to gs://bucket[/prefix] and exit",
    )
    p.add_argument(
        "--restore-from-gcs",
        default=None,
        help="Restore dataset_schema.json and split documents from gs://bucket/prefix into --dest-processor and exit",
    )
    p.add_argument(
        "--import-timeout",
        type=int,
        default=2400,
        help="Timeout in seconds for ImportProcessorVersion LRO (default: 2400s / 40m)",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip step 7 (reading the copy back and checking it against the source). On by default: a failed "
        "check exits 3 and the default is not switched. With --no-verify, --set-default switches without checking.",
    )
    p.add_argument(
        "--source-project-id",
        default=None,
        help="Source GCP project ID for the run log (defaults to the project segment of --source-processor)",
    )
    p.add_argument("--bigquery-project", default=None, help="Project for the BigQuery run log (defaults to the source project)")
    p.add_argument("--bigquery-dataset-id", default=None, help="BigQuery dataset for the run log (logging is off if unset)")
    p.add_argument("--bigquery-table-id", default=None, help="BigQuery table for the run log (logging is off if unset)")
    p.add_argument(
        "--version-map",
        default=None,
        help=(
            "Where to keep the source->destination version-id map: gs://bucket/prefix (recommended: the "
            "Terraform state bucket, e.g. gs://<bucket>/<env>/version_map) or a local directory. One JSON "
            "per destination processor. Without it, versions are matched by display name only (warned)."
        ),
    )
    args = p.parse_args(argv)
    apply_manifest_defaults(args)
    DEFERRED_ERRORS.clear()

    # Standalone mode 1: Snapshot a processor's schema + dataset splits to GCS and exit
    if args.snapshot_to_gcs:
        target_proc_str = args.source_processor or args.dest_processor
        if not target_proc_str:
            p.error("--snapshot-to-gcs requires --source-processor or --dest-processor")
        target_ref = parse_processor(
            target_proc_str,
            default_project=args.dest_project or args.source_project_id,
            default_location=args.dest_location or "us",
        )
        quota_proj = args.dest_project or args.source_project_id or target_ref.project
        os.environ["GOOGLE_CLOUD_QUOTA_PROJECT"] = quota_proj
        ds_client = dataset_client_for(target_ref.location, quota_project_id=quota_proj)
        st_client = storage.Client(project=quota_proj, client_options=ClientOptions(quota_project_id=quota_proj))
        if args.export_schema:
            export_schema_to_file(ds_client, target_ref, args.export_schema)
        snapshot_processor_to_gcs(ds_client, st_client, target_ref, args.snapshot_to_gcs, args.dry_run)
        return 0

    # Standalone mode 2: Restore a processor's schema + dataset splits from a GCS snapshot and exit
    if args.restore_from_gcs:
        if not args.dest_processor:
            p.error("--restore-from-gcs requires --dest-processor")
        target_ref = parse_processor(
            args.dest_processor,
            default_project=args.dest_project,
            default_location=args.dest_location or "us",
        )
        quota_proj = args.dest_project or target_ref.project
        os.environ["GOOGLE_CLOUD_QUOTA_PROJECT"] = quota_proj
        ds_client = dataset_client_for(target_ref.location, quota_project_id=quota_proj)
        st_client = storage.Client(project=quota_proj, client_options=ClientOptions(quota_project_id=quota_proj))
        restore_processor_from_gcs(
            dataset_client=ds_client,
            storage_client=st_client,
            target_ref=target_ref,
            gcs_uri_prefix=args.restore_from_gcs,
            allow_dataset_purge=args.allow_dataset_purge,
            dry_run=args.dry_run,
        )
        return 0

    # Standalone mode 3: Export schema only (when --export-schema is given without --dest-project)
    if args.export_schema and not args.dest_project:
        if not args.source_processor:
            p.error("--export-schema without --dest-project requires --source-processor")
        src_ref = parse_processor(args.source_processor)
        quota_proj = args.source_project_id or src_ref.project
        os.environ["GOOGLE_CLOUD_QUOTA_PROJECT"] = quota_proj
        ds_client = dataset_client_for(src_ref.location, quota_project_id=quota_proj)
        export_schema_to_file(ds_client, src_ref, args.export_schema)
        return 0

    if not args.source_processor or not args.dest_project:
        p.error("--source-processor and --dest-project are required (or pass --manifest)")

    # One BigQuery row per run (skipped for dry runs). run_migration() fills in the
    # fields as it progresses; the row is written in the finally block no matter how
    # the run ends. Logging failures never change the exit code.
    run_row = {
        "execution_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_project_id": args.source_project_id,
        "source_processor_name": None,
        "source_processor_id": None,
        "destination_project_id": args.dest_project,
        "destination_processor_name": None,
        "destination_processor_id": None,
        "default_processor_version": None,
        "dataset_copied": False,
        "source_version_id": None,
        "destination_version_id": None,
        "version_action": None,
        "version_map_uri": None,
        "execution_status": STATUS_FAILED,
        "error_message": None,
        "verification": None,
    }
    bq_enabled = bool(args.bigquery_dataset_id and args.bigquery_table_id) and not args.dry_run

    try:
        return run_migration(args, run_row)
    except SystemExit:
        # Raised by run_preflight_checks() when pre-flight checks fail (exit code 2).
        run_row["execution_status"] = STATUS_PREFLIGHT_FAILED
        run_row["error_message"] = "Pre-flight checks failed. See console output for details."
        raise
    except Exception as e:
        # Errors raised before the main migration try-block (e.g. invalid --source-processor).
        run_row["execution_status"] = STATUS_FAILED
        run_row["error_message"] = _error_summary(str(e))
        raise
    finally:
        if bq_enabled:
            try:
                src_ref = parse_processor(args.source_processor)
            except ValueError:
                src_ref = None
            bq_project = args.bigquery_project or run_row["source_project_id"] or (src_ref.project if src_ref else None)
            bq_location = bigquery_location_for(src_ref.location) if src_ref else "US"
            if bq_project:
                log_run_to_bigquery(
                    run_row, bq_project, args.bigquery_dataset_id, args.bigquery_table_id, bq_location
                )


def run_migration(args: argparse.Namespace, run_row: dict) -> int:
    """Runs the migration, filling in run_row (the BigQuery run log) as it goes. Returns the exit code."""
    os.environ["GOOGLE_CLOUD_QUOTA_PROJECT"] = args.dest_project

    src = parse_processor(args.source_processor)
    dest_location = args.dest_location or src.location
    run_row["source_project_id"] = args.source_project_id or src.project
    run_row["source_processor_id"] = src.processor_id

    run_preflight_checks(
        src=src,
        dest_project_id=args.dest_project,
        dest_location=dest_location,
        copy_dataset=args.copy_dataset,
        dest_dataset_bucket=args.dest_dataset_bucket,
    )

    mode = "specific" if args.version_id else args.versions

    try:
        src_client = client_for(src.location, quota_project_id=args.dest_project)
        dst_client = client_for(dest_location, quota_project_id=args.dest_project)
        dataset_client = dataset_client_for(dest_location, quota_project_id=args.dest_project)

        importable, foundation, pretrained, src_proc = select_source_versions(src_client, src, mode, args.version_id)
        run_row["source_processor_name"] = src_proc.display_name

        print(f"\n{BOLD}Selected Versions to Copy:{RESET}")
        for v in importable:
            print(f"  - Custom Model: {v.display_name} ({v.name.split('/')[-1]})")
        for fv in foundation:
            print(f"  - Pinned Foundation Model: {fv.display_name} ({fv.name.split('/')[-1]})")
        for pv in pretrained:
            print(f"  - Pinned Google Pretrained Version: {pv.name.split('/')[-1]} (pin by ID, no import)")
        if not importable and not foundation and not pretrained:
            log_info("No custom fine-tuned, pinned foundation, or pretrained versions selected.")

        # 1. Ensure destination processor is created or resolved
        dest_proc_name = ensure_destination_processor(
            dst_client,
            args.dest_project,
            dest_location,
            src_proc.type_,
            args.dest_display_name or src_proc.display_name,
            args.dest_processor,
            args.dry_run,
        )
        dest_ref = parse_processor(dest_proc_name, default_project=args.dest_project, default_location=dest_location)
        run_row["destination_processor_name"] = args.dest_display_name or src_proc.display_name
        run_row["destination_processor_id"] = dest_ref.processor_id

        # Safeguard: never migrate a processor into itself. Compare processor ID and
        # location rather than full resource names, because the project segment may be
        # a project number on one side and a project ID on the other.
        if dest_ref.processor_id == src.processor_id and dest_ref.location == src.location:
            raise ValueError(
                f"Destination processor resolves to the source processor ({src.name}). "
                "Aborting before any changes are made. Set a different --dest-display-name "
                "or --dest-processor."
            )

        # 2. Unconditionally initialize destination dataset
        dest_dataset_name = f"{dest_ref.name}/dataset"
        ensure_destination_dataset_initialized(dataset_client, dest_dataset_name, args.dry_run)

        # 3. Copy complete schema (from Git --schema-file if provided, or from source processor)
        copy_dataset_schema(
            dataset_client,
            src,
            dest_ref,
            args.dry_run,
            schema_file=args.schema_file,
            export_schema_path=args.export_schema,
        )

        # 4. Copy dataset documents (if enabled)
        if args.copy_dataset:
            errors_before_dataset = len(DEFERRED_ERRORS)
            copy_dataset_data(
                dataset_client,
                src,
                dest_ref,
                args.dest_dataset_bucket,
                args.dest_project,
                args.dry_run,
                allow_dataset_purge=args.allow_dataset_purge,
            )
            # True only if the dataset step finished without recording any errors (#6, #7b).
            run_row["dataset_copied"] = len(DEFERRED_ERRORS) == errors_before_dataset

        # 5. Import versions (including pinned foundation models when importable)
        #    The version map is the memory of which destination version id came from which
        #    source version id; without it the only link is the (non-unique) display name.
        version_map: Optional[VersionMap] = None
        if args.version_map:
            version_map = VersionMap(args.version_map, dest_ref.name, src.name, args.dest_project)
            run_row["version_map_uri"] = version_map.uri
            log_info(
                f"Version map: {version_map.uri} "
                f"({'new' if version_map.is_empty else str(len(version_map.data['versions'])) + ' pinned version(s)'})"
            )
        else:
            log_info("No --version-map configured; destination versions will be matched by display name.")
        last_v = None
        source_to_dest_version: dict[str, str] = {}
        versions_to_import = list(importable) + list(foundation)
        for v in versions_to_import:
            try:
                imported = import_version(
                    dst_client,
                    dest_proc_name,
                    v,
                    src.location,
                    args.dry_run,
                    import_timeout_seconds=args.import_timeout,
                    version_map=version_map,
                    lineage=run_row,
                )
            except Exception as e:
                if v in foundation:
                    log_info(f"Foundation version '{v.display_name}' is managed via schema/base version ({e}).")
                    continue
                raise

            if imported:
                last_v = imported
                source_to_dest_version[v.name] = imported
                if args.deploy:
                    try:
                        v_obj = dst_client.get_processor_version(name=imported)
                        if v_obj.state == docai.ProcessorVersion.State.DEPLOYING:
                            if not wait_until_deployed(dst_client, imported):
                                raise RuntimeError(
                                    f"Deployment of {v.display_name} ({imported}) failed or timed out."
                                )
                        elif v_obj.state != docai.ProcessorVersion.State.DEPLOYED:
                            t_deploy = time.monotonic()
                            op = dst_client.deploy_processor_version(name=imported)
                            op.result(timeout=1800)
                            log_pass(f"Deployed {v.display_name} (deploy took {_elapsed(t_deploy)})")
                        else:
                            log_info(f"Version {v.display_name} is already deployed.")
                    except Exception as e:
                        _raise_if_deploy_error_is_fatal(e, imported)
                        log_info(f"Deploy notification: {e}")
                        if not wait_until_deployed(dst_client, imported):
                            raise RuntimeError(
                                f"Deployment of {v.display_name} ({imported}) failed or timed out."
                            )

        if args.dry_run and versions_to_import and (args.deploy or args.set_default):
            # import_version() returns None in dry-run, so narrate the steps that would follow.
            steps = [
                s
                for s, on in (
                    ("deploy", args.deploy),
                    ("verify (eight checks)", not args.no_verify),
                    ("set as default", args.set_default),
                )
                if on
            ]
            names = ", ".join(f"'{v.display_name}'" for v in versions_to_import)
            print(f"[dry-run] Would {', then '.join(steps)}: {names}")

        # 5b. Pinned Google pretrained versions (zero-shot): the same version ID exists in the
        #     destination processor, so resolve it there instead of importing. Only when nothing
        #     custom was selected does it become the default candidate; otherwise it is only used
        #     if it is the source's default (step 6).
        for pv in pretrained:
            pv_id = pv.name.split("/")[-1]
            dest_pv_name = f"{dest_proc_name}/processorVersions/{pv_id}"
            if args.dry_run:
                print(f"[dry-run] Would pin destination default to pretrained version {pv_id}")
                continue
            try:
                dest_pv = dst_client.get_processor_version(name=dest_pv_name)
            except NotFound:
                log_deferred_error(
                    f"Pretrained version {pv_id} is not available on destination processor {dest_proc_name}. "
                    "The destination cannot be pinned to the same model as the source."
                )
                continue
            source_to_dest_version[pv.name] = dest_pv.name
            if not importable and not foundation:
                last_v = dest_pv.name
            log_pass(f"Resolved pretrained version {pv_id} in destination (state: {dest_pv.state.name}).")

        # 6. Choose the version that becomes the default (the one matching the source's
        #    default_processor_version; otherwise the explicitly selected version in specific mode or
        #    the last imported one) and deploy it - but do NOT make it the default yet. A deployed
        #    version can be called by its ID, so step 7 verifies it while production keeps serving the
        #    current default, and step 8 switches only when every check passed.
        target_default_v = source_to_dest_version.get(src_proc.default_processor_version, last_v)
        if mode == "specific" and last_v:
            target_default_v = last_v
        if target_default_v and args.deploy:
            deploy_and_default(dst_client, dest_proc_name, target_default_v, True, False, args.dry_run)

        # 7. Verify the copy: read it back and compare it with the source (eight checks). A failed
        #    check - or a verification that could not run - is an error of this run (exit 3), so
        #    the Terraform apply (and the CI run) goes red, and step 8 leaves the default alone.
        #    --no-verify skips it; dry runs skip it.
        verified: Optional[bool] = None
        if args.no_verify:
            run_row["verification"] = "SKIPPED"
            log_info("Verification skipped (--no-verify).")
        elif args.dry_run:
            print("[dry-run] Would verify the copy before it becomes the default: eight read-only checks against the source")
        else:
            dest_to_source = {d: s for s, d in source_to_dest_version.items()}
            try:
                checks, infos = verify_copy(
                    src_client, dst_client, dataset_client, src, dest_ref, src_proc,
                    dest_to_source.get(target_default_v) if target_default_v else None, target_default_v,
                    expect_deployed=args.deploy or args.set_default, expect_default=False,
                    schema_file=args.schema_file,
                )
                failed = print_verification(checks, infos)
                if failed:
                    verified = False
                    run_row["verification"] = ("FAIL: " + "; ".join(failed))[:_BQ_ERROR_MESSAGE_MAX_LEN]
                    log_deferred_error(f"Verification: {len(failed)} of {len(checks)} checks failed - {'; '.join(failed)}")
                else:
                    verified = True
                    run_row["verification"] = f"PASS {len(checks)}/{len(checks)}"
            except Exception as e:
                verified = False
                run_row["verification"] = f"ERROR: {e}"[:_BQ_ERROR_MESSAGE_MAX_LEN]
                log_deferred_error(f"Verification could not be completed: {e}")

        # 8. Set as default - only after every check passed (or with --no-verify), then confirm.
        switch_problem = switch_default_after_verification(
            dst_client, dest_proc_name, target_default_v,
            deploy=args.deploy, set_default=args.set_default, verified=verified,
            dry_run=args.dry_run, run_row=run_row,
        )
        if target_default_v and args.set_default and not args.dry_run:
            if switch_problem:
                suffix = "; FAIL: default not switched"
                log_deferred_error(f"Default switch not confirmed: {switch_problem}")
            elif verified is False:
                suffix = "; default unchanged"
            else:
                suffix = "; default switched"
            run_row["verification"] = ((run_row.get("verification") or "") + suffix)[:_BQ_ERROR_MESSAGE_MAX_LEN]

        if DEFERRED_ERRORS:
            run_row["execution_status"] = STATUS_COMPLETED_WITH_ERRORS
            run_row["error_message"] = _error_summary(*DEFERRED_ERRORS)
            print(f"\n{RED}{BOLD}{'=' * 75}{RESET}")
            print(f"{RED}{BOLD}✗ PROCESSOR MIGRATION COMPLETED WITH {len(DEFERRED_ERRORS)} ERROR(S):{RESET}")
            for i, err in enumerate(DEFERRED_ERRORS, start=1):
                print(f"  {i}. {err}")
            print(f"Destination Processor: {BOLD}{dest_proc_name}{RESET}")
            print(f"{RED}{BOLD}{'=' * 75}{RESET}\n")
            return 3

        run_row["execution_status"] = STATUS_SUCCESS
        print(f"\n{GREEN}{BOLD}{'=' * 75}{RESET}")
        print(f"{GREEN}{BOLD}✓ PROCESSOR MIGRATION COMPLETED SUCCESSFULLY!{RESET}  (total {_elapsed(_RUN_T0)})")
        print(f"Destination Processor: {BOLD}{dest_proc_name}{RESET}")
        print(f"{GREEN}{BOLD}{'=' * 75}{RESET}\n")
        return 0

    except Exception as e:
        run_row["execution_status"] = STATUS_FAILED
        run_row["error_message"] = _error_summary(str(e), *DEFERRED_ERRORS)
        log_fail(f"Execution failed: {e}")
        if DEFERRED_ERRORS:
            print(f"{RED}Errors recorded earlier in this run:{RESET}")
            for i, err in enumerate(DEFERRED_ERRORS, start=1):
                print(f"  {i}. {err}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
