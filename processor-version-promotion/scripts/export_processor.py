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
Exports a Document AI processor's live DatasetSchema and approved version metadata
from the Source/Training project into Git-tracked files:
  - schemas/<processor_key>/<version-display-name>.schema.json
  - manifests/<env>/<processor_key>.yaml

With --open-pr it also commits those files on a promote/<env>/<key>-<version> branch,
pushes, and opens the pull request (the approval gate; plan.yml comments the Terraform
plan on it, merging runs apply.yml). Optionally takes a restorable GCS snapshot
(schema + split-categorized documents) of the source processor at the same time.
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

# gRPC prints info-level "FD from fork parent still in poll list" lines when a process that has
# used a gRPC channel later forks (git/gh subprocesses below). Harmless; silence before import.
os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
os.environ.setdefault("GRPC_ENABLE_FORK_SUPPORT", "false")

from google.api_core.client_options import ClientOptions  # noqa: E402
from google.cloud import storage  # noqa: E402

from copy_processor import (
    BOLD,
    GREEN,
    RESET,
    client_for,
    dataset_client_for,
    export_schema_to_file,
    log_check,
    log_info,
    log_pass,
    parse_processor,
    snapshot_processor_to_gcs,
)


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Export a Document AI processor's schema.json and release manifest YAML for Git tracking."
    )
    p.add_argument(
        "--source-processor",
        required=True,
        help="Full resource name: projects/<project>/locations/<location>/processors/<id>",
    )
    p.add_argument(
        "--processor-key",
        required=True,
        help="Short identifier for Git files (e.g. 'invoice_extractor' -> schemas/invoice_extractor.schema.json)",
    )
    p.add_argument(
        "--env",
        default="qa",
        help="Target environment folder under manifests/ (default: 'qa')",
    )
    p.add_argument(
        "--manifests-dir",
        default=None,
        help="Directory for the manifest instead of manifests/<env> (e.g. environments/qa/manifests). "
             "Must match the manifests_dir Terraform variable of that environment's stack.",
    )
    p.add_argument(
        "--version-id",
        default=None,
        help="Specific source processor version ID to pin (defaults to the source processor's default version)",
    )
    p.add_argument(
        "--dest-display-name",
        default=None,
        help="Display name for the destination processor (defaults to source processor display name)",
    )
    p.add_argument(
        "--quota-project",
        default=None,
        help="Quota project ID for ADC (defaults to the project in --source-processor)",
    )
    p.add_argument(
        "--snapshot-to-gcs",
        default=None,
        help="Optional GCS URI (gs://bucket[/prefix]) to also snapshot the source dataset & schema",
    )
    p.add_argument(
        "--rewrite-manifest",
        action="store_true",
        help="Regenerate the whole manifest instead of only updating the version/schema lines of an existing one",
    )
    p.add_argument(
        "--open-pr",
        action="store_true",
        help="After export: create branch promote/<env>/<key>-<version>, commit the two files, push, and open a "
        "GitHub pull request with gh. plan.yml runs on the PR; merging runs apply.yml.",
    )
    p.add_argument("--git-remote", default="origin", help="Git remote to push the promotion branch to (default: origin)")
    p.add_argument("--base-branch", default="main", help="Pull request base branch (default: main)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    src_ref = parse_processor(args.source_processor)
    quota_proj = args.quota_project or src_ref.project
    os.environ["GOOGLE_CLOUD_QUOTA_PROJECT"] = quota_proj

    proc_client = client_for(src_ref.location, quota_project_id=quota_proj)
    ds_client = dataset_client_for(src_ref.location, quota_project_id=quota_proj)

    log_check(f"Inspecting source processor {src_ref.name}...")
    proc = proc_client.get_processor(name=src_ref.name)
    # Key by short version ID: the API returns resource names using the project *number*
    # (projects/1234/...), so matching on full names built from the project ID would miss.
    versions = {v.name.split("/")[-1]: v for v in proc_client.list_processor_versions(parent=src_ref.name)}

    default_short = proc.default_processor_version.split("/")[-1] if proc.default_processor_version else ""
    if args.dry_run or not args.version_id:
        log_info(
            f"Source '{proc.display_name}' ({proc.type_}): {len(versions)} version(s), "
            f"default = {default_short or 'none'}"
        )
        for vid, v in sorted(versions.items(), key=lambda kv: str(kv[1].create_time or "")):
            kind = "google-managed" if v.google_managed else "custom"
            state = getattr(v.state, "name", str(v.state))
            marker = "  <- default" if vid == default_short else ""
            print(f"      {vid:<50} {v.display_name[:32]:<32} {state:<11} {kind}{marker}")

    if args.version_id:
        full_ver_name = (
            args.version_id
            if args.version_id.startswith("projects/")
            else f"{src_ref.name}/processorVersions/{args.version_id}"
        )
    else:
        full_ver_name = proc.default_processor_version

    short_ver_id = full_ver_name.split("/")[-1] if full_ver_name else ""
    ver_obj = versions.get(short_ver_id) if short_ver_id else None
    if short_ver_id and ver_obj is None:
        print(f"  [WARN] Version {short_ver_id} not found on source processor; available: {sorted(versions)}")
    ver_display_name = ver_obj.display_name if ver_obj else ""

    log_info(
        f"Pinning version {short_ver_id or '(none)'}"
        + (f" ('{ver_display_name}')" if ver_display_name else "")
        + ("" if args.version_id else " — the source default; pass --version-id to pin another")
    )
    custom_ids = [vid for vid, v in versions.items() if not v.google_managed]
    if not args.version_id and ver_obj is not None and ver_obj.google_managed and custom_ids:
        print(
            f"  [WARN] The source default is a Google-managed version, but this processor also has "
            f"custom-trained version(s): {', '.join(custom_ids)}. If the trained model is what should be "
            f"promoted, re-run with --version-id <one of these>."
        )

    # One schema file per approved version, never edited in place. QA and prod manifests
    # each point at their own file, so a schema change reaches prod only when the prod
    # manifest is changed, not when a shared file is edited.
    # Google-managed (pretrained) versions share display names such as "Google Stable",
    # so they are tagged by version ID instead. Custom names are sanitized for file paths.
    if ver_obj is not None and ver_obj.google_managed:
        schema_tag = short_ver_id
    else:
        schema_tag = re.sub(r"[^A-Za-z0-9._-]+", "-", ver_display_name).strip("-") or short_ver_id
    schema_rel_path = (
        f"schemas/{args.processor_key}/{schema_tag}.schema.json"
        if schema_tag
        else f"schemas/{args.processor_key}/{args.processor_key}.schema.json"
    )
    manifests_dir = (args.manifests_dir or f"manifests/{args.env}").strip("/")
    manifest_rel_path = f"{manifests_dir}/{args.processor_key}.yaml"

    if args.dry_run:
        log_info(f"[dry-run] Would export schema to {schema_rel_path} and manifest to {manifest_rel_path}")
        return 0

    if args.open_pr:
        # Merges and reverts happen in the browser, so the laptop's base branch is usually behind.
        # Compare against what GitHub has, not against a stale local checkout.
        _sync_base_branch(args.git_remote, args.base_branch)

    export_schema_to_file(ds_client, src_ref, schema_rel_path)

    manifest_path = Path(manifest_rel_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_display = args.dest_display_name or proc.display_name
    version_kind = (
        "google pretrained (pinned by ID, no import)"
        if ver_obj is not None and ver_obj.google_managed
        else "custom (ImportProcessorVersion)"
    )
    if manifest_path.is_file() and not args.rewrite_manifest:
        # Re-promotion: touch only the release lines so the pull-request diff is the version bump
        # and nothing else (hand edits such as existing_processor_id or deploy flags survive).
        existing = manifest_path.read_text(encoding="utf-8")
        updated = existing
        for key, value in (
            ("source_version_id", short_ver_id),
            ("version_display_name", ver_display_name),
            ("schema_file", schema_rel_path),
        ):
            pattern = re.compile(rf"^{key}:.*$", re.M)
            if pattern.search(updated):
                updated = pattern.sub(f'{key}: "{value}"', updated, count=1)
            else:
                updated = updated.rstrip("\n") + f'\n{key}: "{value}"\n'
        if updated == existing:
            log_info(f"Manifest {manifest_path} already pins {short_ver_id}; no change.")
        else:
            manifest_path.write_text(updated, encoding="utf-8")
            log_pass(f"Updated release lines in existing manifest {manifest_path}")
    else:
        manifest_content = (
            f"# Declarative Document AI Processor Manifest ({args.env})\n"
            f"processor_key: \"{args.processor_key}\"\n"
            f"display_name: \"{dest_display}\"\n"
            f"processor_type: \"{proc.type_}\"\n"
            f"# Day 0 only: set to the ID of a destination processor that already exists so Terraform\n"
            f"# adopts it instead of creating a new one. Delete this line after the first apply.\n"
            f"# existing_processor_id: \"\"\n"
            f"location: \"{src_ref.location}\"\n"
            f"source_project_id: \"{src_ref.project}\"\n"
            f"source_processor: \"{src_ref.name}\"\n"
            f"# Approved version to promote ({version_kind}). versions_mode is only used when this is empty.\n"
            f"source_version_id: \"{short_ver_id}\"\n"
            f"version_display_name: \"{ver_display_name}\"\n"
            f"versions_mode: \"default\"\n"
            f"schema_file: \"{schema_rel_path}\"\n"
            f"deploy: true\n"
            f"set_default: true\n"
            f"copy_dataset: false\n"
        )
        manifest_path.write_text(manifest_content, encoding="utf-8")
        log_pass(f"Wrote release manifest to {manifest_path}")

    if args.snapshot_to_gcs:
        st_client = storage.Client(project=quota_proj, client_options=ClientOptions(quota_project_id=quota_proj))
        snapshot_processor_to_gcs(ds_client, st_client, src_ref, args.snapshot_to_gcs, dry_run=False)

    if args.open_pr:
        return open_pull_request(
            files=[schema_rel_path, manifest_rel_path],
            env=args.env,
            processor_key=args.processor_key,
            dest_display=dest_display,
            source_processor=src_ref.name,
            version_id=short_ver_id,
            version_display=ver_display_name or short_ver_id,
            version_kind=version_kind,
            remote=args.git_remote,
            base=args.base_branch,
        )

    print(f"\n{GREEN}{BOLD}✓ Export complete! Commit {schema_rel_path} and {manifest_rel_path} to Git.{RESET}")
    return 0


# ---------------------------------------------------------------------------
# --open-pr: branch, commit, push, pull request. The pull request is the approval gate;
# plan.yml runs on it automatically and apply.yml runs on merge.
# ---------------------------------------------------------------------------
def _git(*args: str, check: bool = True, capture: bool = True) -> str:
    res = subprocess.run(["git", *args], text=True, capture_output=capture, check=False)
    if check and res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {(res.stderr or res.stdout).strip()}")
    return (res.stdout or "").strip()


def _github_repo_from_remote(remote: str) -> str:
    url = _git("remote", "get-url", remote)
    m = re.search(r"github\.com[:/]([^/]+/[^/.]+?)(?:\.git)?/?$", url)
    if not m:
        raise RuntimeError(f"Remote {remote!r} ({url}) is not a GitHub URL; use --git-remote to pick one.")
    return m.group(1)


def _sync_base_branch(remote: str, base: str) -> None:
    """Fast-forward the local base branch from the remote so the diff is against GitHub's state.

    Merges and reverts are done in the browser; the local checkout learns about them only here.
    Fast-forward only: never rewrites local work. If the user is on another branch, or the
    fast-forward is not possible, say so and carry on with the local state.
    """
    current = _git("rev-parse", "--abbrev-ref", "HEAD")
    if current != base:
        print(f"  [WARN] On branch {current!r}, not {base!r}: comparing against the local branch, not {remote}/{base}.")
        return
    try:
        _git("fetch", "-q", remote, base)
        before = _git("rev-parse", "HEAD")
        _git("merge", "-q", "--ff-only", "FETCH_HEAD")
        after = _git("rev-parse", "HEAD")
        if before != after:
            log_info(f"Fast-forwarded {base} to {remote}/{base} ({after[:7]}) before comparing.")
    except RuntimeError as e:
        print(f"  [WARN] Could not fast-forward {base} from {remote}: {e}. Comparing against the local checkout.")


def open_pull_request(
    *,
    files: list[str],
    env: str,
    processor_key: str,
    dest_display: str,
    source_processor: str,
    version_id: str,
    version_display: str,
    version_kind: str,
    remote: str,
    base: str,
) -> int:
    if shutil.which("gh") is None:
        print("  [FAILED] --open-pr needs the GitHub CLI (gh) on PATH and `gh auth login` done.")
        return 1
    repo = _github_repo_from_remote(remote)
    original_branch = _git("rev-parse", "--abbrev-ref", "HEAD")

    # Anything to promote? Compare the generated files with HEAD before creating a branch.
    if not _git("status", "--porcelain", "--", *files):
        log_info(
            f"{', '.join(files)} match the committed state; nothing to promote, no pull request opened. "
            f"({base} already pins this version; if you expected a change, check `git log -1 -- {files[1]}`.)"
        )
        return 0

    tag = re.sub(r"[^A-Za-z0-9._-]+", "-", version_display).strip("-") or version_id
    branch = f"promote/{env}/{processor_key}-{tag}"
    if _git("rev-parse", "--verify", "--quiet", branch, check=False):
        branch = f"{branch}-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}"

    log_check(f"Opening pull request on {repo}: {branch} -> {base}")
    _git("checkout", "-b", branch)
    try:
        _git("add", "--", *files)
        title = f"promote({env}): {processor_key} -> {version_display} ({version_id})"
        body = (
            f"## Promote `{processor_key}` to **{env}**\n\n"
            f"| | |\n|---|---|\n"
            f"| Destination processor | `{dest_display}` |\n"
            f"| Source processor | `{source_processor}` |\n"
            f"| Pinned version | `{version_display}` (`{version_id}`) — {version_kind} |\n"
            f"| Schema file | `{files[0]}` |\n"
            f"| Manifest | `{files[1]}` |\n\n"
            f"Generated by `scripts/export_processor.py --open-pr`. "
            f"`plan.yml` posts the Terraform plan below; merging runs `apply.yml` for `{env}`.\n"
        )
        _git("commit", "-q", "-m", title, "-m", body)
        _git("push", "-q", "-u", remote, branch)
        res = subprocess.run(
            ["gh", "pr", "create", "--repo", repo, "--base", base, "--head", branch, "--title", title, "--body", body],
            text=True, capture_output=True, check=False,
        )
        if res.returncode != 0:
            raise RuntimeError(f"gh pr create failed: {(res.stderr or res.stdout).strip()}")
        pr_url = res.stdout.strip().splitlines()[-1]
    finally:
        # Leave the working tree where the user started; the change lives on the pushed branch.
        _git("checkout", "-q", original_branch, check=False)

    print(f"\n{GREEN}{BOLD}✓ Pull request opened: {pr_url}{RESET}")
    print(f"  Review the plan comment, approve and merge to apply to {env}. Local branch: {original_branch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
