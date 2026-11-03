#!/usr/bin/env bash
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

# =============================================================================================
# bootstrap/setup_cicd.sh — one-time setup so GitHub Actions can run `terraform plan/apply`
# (which in turn runs scripts/copy_processor.py) against a destination project WITHOUT any
# service-account key.
#
#   ./bootstrap/setup_cicd.sh --project <destination-project> --github <owner/repo> --env <qa|prod>
#   ./bootstrap/setup_cicd.sh --project <gcp-project> --github <owner/repo>      # one project, qa+prod as state prefixes
#   add --source <training-project> (repeatable) to also grant, on each source, what the destination
#   needs to import from it
#
# Besides the cloud resources it writes the environment's Git-tracked file, environments/<env>.tfvars
# (see environments/README.md): commit it.
# Idempotent: every step checks before creating; safe to re-run after a partial failure.
#
# Steps
#   0  prerequisite checks      caller needs project Editor + Project IAM Admin + Workload Identity
#                               Pool Admin on the destination project
#   1  APIs                     documentai, storage, iam, iamcredentials, sts, cloudresourcemanager
#                               (+ bigquery for the run log)
#   2  service account          docai-promoter + its roles on the destination project
#   3  state bucket             versioned gs://<project>-tfstate (Terraform state and the version map)
#   4  Workload Identity        pool + OIDC provider for GitHub, restricted to one repository
#   4c --source grants          on each training project: Document AI service agent = documentai.editor,
#                               docai-promoter = documentai.viewer (+ BigQuery); printed for the
#                               source owner when the caller has no IAM admin there
#   4d environments/<env>.tfvars  values from the steps above; commit it
#   5  GitHub settings          Environment variables WIF_PROVIDER, GCP_SERVICE_ACCOUNT, TF_STATE_BUCKET
#                               (needs the gh CLI; --skip-ci-config prints them instead)
#
# Another CI system with OIDC tokens (GitLab, Cloud Build, ...) only needs a different issuer,
# attribute mapping and condition in the "OIDC profile" block below.
#
# Several projects (training / qa / prod): run this once per destination project, each with its own
# state bucket, and pass the training project with --source. Each destination project must have
# billing enabled (DeployProcessorVersion needs it).
#
# Not covered (environment policy): billing accounts, organization policies, VPC Service Controls.
# =============================================================================================
set -euo pipefail
export CLOUDSDK_CORE_DISABLE_PROMPTS=1   # unattended: never wait on a gcloud prompt (component install, confirmations)

# ----------------------------------------------------------------------------- arguments ----
PROJECT="" ; GITHUB_REPO="" ; SOURCES=()
BUCKET="" ; LOCATION="us" ; SA_NAME="docai-promoter" ; POOL="cicd" ; PROVIDER=""
BQ_DATASET="docai_migration_logs" ; SKIP_CI_CONFIG=0 ; GH_ENV=""
while [ $# -gt 0 ]; do
  case "$1" in
    --project)   PROJECT="$2"; shift 2;;
    --source)    SOURCES+=("$2"); shift 2;;      # source project(s) this destination imports from; repeatable
    --github)    GITHUB_REPO="$2"; shift 2;;
    --bucket)    BUCKET="$2"; shift 2;;
    --location)  LOCATION="$2"; shift 2;;
    --sa-name)   SA_NAME="$2"; shift 2;;
    --pool)      POOL="$2"; shift 2;;
    --env)       GH_ENV="$2"; shift 2;;
    --no-bq)     BQ_DATASET=""; shift;;
    --skip-ci-config) SKIP_CI_CONFIG=1; shift;;
    -h|--help)   sed -n '16,/^# =\{20,\}$/p' "$0"; exit 0;;
    *) echo "unknown argument: $1" >&2; exit 2;;
  esac
done
[ -n "$PROJECT" ] || { echo "--project is required" >&2; exit 2; }
[ -n "$GITHUB_REPO" ] || { echo "--github <owner/repo> is required" >&2; exit 2; }
BUCKET="${BUCKET:-${PROJECT}-tfstate}"
SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"

# ------------------------------------------------------------------------------ OIDC profile ---
# Everything that differs between CI systems is in this block and nowhere else.
CI_NAME="GitHub Actions"
PROVIDER="${PROVIDER:-github}"
ISSUER="https://token.actions.githubusercontent.com"
ALLOWED_AUDIENCES=""      # google-github-actions/auth requests the provider's own name as audience (Google's default)
# GitHub token claims: sub, repository, ref, actor, ...
ATTR_MAPPING="google.subject=assertion.sub,attribute.repository=assertion.repository"
ATTR_CONDITION="assertion.repository=='${GITHUB_REPO}'"
PRINCIPAL_SUFFIX="attribute.repository/${GITHUB_REPO}"

log() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
ok()  { printf '   \033[32m✓\033[0m %s\n' "$*"; }
warn(){ printf '   \033[33m!\033[0m %s\n' "$*"; }
# IAM reads lag writes by a few seconds (new SA, new pool): retry bindings on a fresh principal.
retry() { local n=0; until "$@"; do n=$((n+1)); [ $n -ge 6 ] && return 1; sleep 10; done; }
retry3() { local n=0; until "$@"; do n=$((n+1)); [ $n -ge 3 ] && return 1; sleep 5; done; }   # new principals: IAM lag of a few seconds

# ------------------------------------------------------------------------- 0. prerequisites --
log "0/5 Prerequisites (project ${PROJECT}, CI = ${CI_NAME})"
command -v gcloud >/dev/null || { echo "gcloud not found" >&2; exit 1; }
if [ "$SKIP_CI_CONFIG" = 0 ]; then command -v gh >/dev/null || { echo "gh (GitHub CLI) not found; use --skip-ci-config to set variables by hand" >&2; exit 1; }; fi
CALLER=$(gcloud config get-value account 2>/dev/null)
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
ok "caller ${CALLER}, project number ${PROJECT_NUMBER}"
# Project Editor cannot create WIF pools; grant Workload Identity Pool Admin to the caller first
# if needed (an Editor who can set IAM policy may grant it to themselves):
#   gcloud projects add-iam-policy-binding $PROJECT --member=user:$CALLER --role=roles/iam.workloadIdentityPoolAdmin
if ! gcloud iam workload-identity-pools list --project="$PROJECT" --location=global >/dev/null 2>&1; then
  warn "caller cannot list WIF pools; step 4 will fail without roles/iam.workloadIdentityPoolAdmin"
fi
# stdin is closed so gcloud cannot block on an "enable the Cloud Billing API and retry?" prompt
# (that API lives in the caller's gcloud quota project, not in $PROJECT); a failure is only a warning.
BILLING=$(gcloud billing projects describe "$PROJECT" --format='value(billingEnabled)' --quiet </dev/null 2>/dev/null || true)
case "$BILLING" in
  True)  ok "billing enabled" ;;
  False) warn "billing is NOT linked on ${PROJECT} — ImportProcessorVersion works, DeployProcessorVersion will fail with BILLING_DISABLED" ;;
  *)     warn "could not check billing (Cloud Billing API not enabled for the caller, or no permission) — verify DeployProcessorVersion is allowed on ${PROJECT}" ;;
esac

# ------------------------------------------------------------------------------- 1. APIs -----
log "1/5 APIs"
gcloud services enable documentai.googleapis.com storage.googleapis.com iam.googleapis.com \
  iamcredentials.googleapis.com sts.googleapis.com cloudresourcemanager.googleapis.com \
  ${BQ_DATASET:+bigquery.googleapis.com} --project="$PROJECT" --quiet
ok "enabled"
# The Document AI service agent (service-<number>@gcp-sa-prod-dai-core) is the identity that performs
# ImportProcessorVersion for this project. It is created lazily; create it now so the source-side
# grant below has an existing member to bind. (Service Usage REST call: no gcloud beta component needed.)
DEST_AGENT="service-${PROJECT_NUMBER}@gcp-sa-prod-dai-core.iam.gserviceaccount.com"
if curl -sf -o /dev/null -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" \
     "https://serviceusage.googleapis.com/v1beta1/projects/${PROJECT}/services/documentai.googleapis.com:generateServiceIdentity"; then
  ok "Document AI service agent ${DEST_AGENT}"
else
  warn "could not pre-create the Document AI service agent — it appears after the first Document AI call in ${PROJECT}; re-run the source grants then"
fi

# ---------------------------------------------------------------------- 2. service account ---
log "2/5 Pipeline service account ${SA}"
if ! gcloud iam service-accounts describe "$SA" --project="$PROJECT" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" --project="$PROJECT" --display-name="Document AI promoter (CI/CD)" --quiet
  ok "created"
else ok "exists"; fi
ROLES=(roles/documentai.editor               # create processors, import/deploy versions, dataset schema
       roles/serviceusage.serviceUsageConsumer # use the project as quota project
       roles/browser)                         # resourcemanager.projects.get for data.google_project
[ -n "$BQ_DATASET" ] && ROLES+=(roles/bigquery.jobUser roles/bigquery.dataEditor)   # optional run log
for role in "${ROLES[@]}"; do
  retry gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:${SA}" --role="$role" --condition=None --quiet >/dev/null
  ok "$role"
done

# ------------------------------------------------------------------------- 3. state bucket ---
log "3/5 Terraform state bucket gs://${BUCKET}"
if ! gcloud storage buckets describe "gs://${BUCKET}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUCKET}" --project="$PROJECT" --location="$LOCATION" --uniform-bucket-level-access --public-access-prevention
  ok "created"
else ok "exists"; fi
gcloud storage buckets update "gs://${BUCKET}" --versioning >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" --member="serviceAccount:${SA}" --role=roles/storage.objectAdmin >/dev/null
ok "versioning on; SA is objectAdmin"

# ------------------------------------------------------------- 4. Workload Identity Federation
log "4/5 Workload Identity Federation: pool ${POOL}, provider ${PROVIDER}, issuer ${ISSUER}"
if ! gcloud iam workload-identity-pools describe "$POOL" --project="$PROJECT" --location=global >/dev/null 2>&1; then
  retry gcloud iam workload-identity-pools create "$POOL" --project="$PROJECT" --location=global --display-name="CI/CD OIDC" --quiet
  ok "pool created"
else ok "pool exists"; fi
if ! gcloud iam workload-identity-pools providers describe "$PROVIDER" --project="$PROJECT" --location=global --workload-identity-pool="$POOL" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" --project="$PROJECT" --location=global \
    --workload-identity-pool="$POOL" --display-name="$CI_NAME" --issuer-uri="$ISSUER" \
    ${ALLOWED_AUDIENCES:+--allowed-audiences="$ALLOWED_AUDIENCES"} \
    --attribute-mapping="$ATTR_MAPPING" --attribute-condition="$ATTR_CONDITION" --quiet
  ok "provider created"
else ok "provider exists (issuer/mapping not changed; delete it to recreate)"; fi
PRINCIPAL="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/${PRINCIPAL_SUFFIX}"
# (a) the CI identity may impersonate the pipeline SA
retry gcloud iam service-accounts add-iam-policy-binding "$SA" --project="$PROJECT" --role=roles/iam.workloadIdentityUser --member="$PRINCIPAL" --quiet >/dev/null
ok "workloadIdentityUser on ${SA_NAME} for ${PRINCIPAL_SUFFIX}"
# (b) the CI identity may bill the token exchange to the project. Without this the Python client
#     libraries fail with USER_PROJECT_DENIED on iamcredentials.googleapis.com (Terraform's own
#     provider does not send the quota-project header, so only copy_processor.py would fail).
retry gcloud projects add-iam-policy-binding "$PROJECT" --member="$PRINCIPAL" --role=roles/serviceusage.serviceUsageConsumer --condition=None --quiet >/dev/null
ok "serviceUsageConsumer on project for the CI identity"
WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"

# ------------------------------------------------------------ 4c. source-side grants (--source) --
# Two identities need rights on each SOURCE project this destination imports from:
#   (1) the destination's Document AI service agent — ImportProcessorVersion runs as it inside the destination
#       and reads the model out of the source: roles/documentai.editor (the role Google documents for cross-project import);
#   (2) docai-promoter — reads the processor, its versions and dataset schema: roles/documentai.viewer
#       (+ the two BigQuery roles when the run log table lives in the source project, the default layout).
# Done here when the caller has IAM admin on the source; otherwise the exact commands are printed for its owner.
TODO_SOURCE=()
if [ ${#SOURCES[@]} -gt 0 ]; then
  log "4c  Source-side grants for ${#SOURCES[@]} source project(s)"
  for SRC in "${SOURCES[@]}"; do
    [ "$SRC" = "$PROJECT" ] && { ok "${SRC}: same project as the destination, nothing to grant"; continue; }
    GRANTS=("serviceAccount:${DEST_AGENT}|roles/documentai.editor" "serviceAccount:${SA}|roles/documentai.viewer")
    [ -n "$BQ_DATASET" ] && GRANTS+=("serviceAccount:${SA}|roles/bigquery.jobUser" "serviceAccount:${SA}|roles/bigquery.dataEditor")
    for g in "${GRANTS[@]}"; do
      member="${g%%|*}"; role="${g##*|}"
      if retry3 gcloud projects add-iam-policy-binding "$SRC" --member="$member" --role="$role" --condition=None --quiet >/dev/null 2>&1; then
        ok "${SRC}: ${role} -> ${member#serviceAccount:}"
      else
        warn "${SRC}: cannot bind ${role} for ${member#serviceAccount:} (no IAM admin there?) — for the source owner:"
        TODO_SOURCE+=("gcloud projects add-iam-policy-binding ${SRC} --member=${member} --role=${role}")
      fi
    done
  done
else
  warn "no --source given: the grants on the source project(s) are listed at the end for their owner"
fi

# ------------------------------------------------- 4d. environment file (the Git-tracked half) ---
# Everything Terraform needs to know about an environment lives in one small committed file,
# environments/<env>.tfvars (nothing in it is secret): destination project, manifests folder, version
# map, run log, interpreter. GitHub keeps only the identity and the state bucket. An existing file is
# never overwritten: a differing version goes to bootstrap/out/ to diff.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -n "$GH_ENV" ]; then ENV_NAMES=("$GH_ENV"); else ENV_NAMES=(qa prod); fi   # no --env: qa+prod as two prefixes in this project
ENV_FILES=()
place_file() {   # <generated file> <target, relative to the repository root>
  if [ ! -f "${REPO_ROOT}/$2" ]; then mv "$1" "${REPO_ROOT}/$2"; ok "wrote $2"
  elif cmp -s "$1" "${REPO_ROOT}/$2"; then rm -f "$1"; ok "$2 unchanged"
  else mv "$1" "${REPO_ROOT}/bootstrap/out/$(basename "$2")"; warn "$2 exists and differs: new version in bootstrap/out/$(basename "$2") — diff, then move it yourself"; fi
  ENV_FILES+=("$2")
}
log "4d  Environment file (environments/<env>.tfvars, to commit)"
mkdir -p "${REPO_ROOT}/environments" "${REPO_ROOT}/bootstrap/out"
for ENV_NAME in "${ENV_NAMES[@]}"; do
  TMP_TFVARS="$(mktemp)"
  cat >"$TMP_TFVARS" <<EOT
# environments/${ENV_NAME}.tfvars — everything Terraform needs to know about the ${ENV_NAME} environment.
# Written by bootstrap/setup_cicd.sh --project ${PROJECT} --env ${ENV_NAME}; edit and commit like any other file.
# One environment = one destination project. Sources are declared per processor in manifests_dir.
#
#   terraform plan -var-file=environments/${ENV_NAME}.tfvars          (workstation / Cloud Shell)
#   GitHub Actions: plan.yml / apply.yml pass the same -var-file per matrix entry
#
# Nothing here is secret. Credentials never go here (the identity lives in the CI system), nor does
# anything per processor (that is the manifest). GitHub Actions keeps the Terraform state in the
# bucket below (TF_STATE_BUCKET on the GitHub Environment).

destination_project_id = "${PROJECT}"
destination_location   = "us" # Document AI location of the destination processors: us or eu

# Processor manifests promoted into this environment: one *.yaml per processor,
# written by \`scripts/export_processor.py --env ${ENV_NAME}\`.
manifests_dir = "manifests/${ENV_NAME}"

# Memory of which destination version came from which source version
# (see VersionMap in scripts/copy_processor.py). A prefix in the bucket this script created.
version_map_uri = "gs://${BUCKET}/${ENV_NAME}/version_map"

# Run log: one BigQuery row per run, in the SOURCE project. Set bigquery_dataset_id = "" to turn it off.
bigquery_dataset_id = "${BQ_DATASET}"
bigquery_table_id   = "migration_events"

# Interpreter that runs scripts/copy_processor.py (scripts/requirements.txt installed for it).
python_bin = "python3"

# true = re-run every processor on the next apply even if nothing changed in Git (one-off repair; set back to false).
force_reconcile = false
EOT
  place_file "$TMP_TFVARS" "environments/${ENV_NAME}.tfvars"
  mkdir -p "${REPO_ROOT}/manifests/${ENV_NAME}"
done

# ------------------------------------------------------------------- 5. GitHub settings -------
# GitHub holds the *identity* (which WIF provider to present a token to, which service account to
# impersonate) and the state bucket. With --env <name> they become GitHub *Environment* variables
# (both workflows bind `environment: ${{ matrix.environment }}`), so each environment can be a
# different project; without --env they are repository variables (single-project layout: qa and prod
# are two state prefixes in one project). Project, manifests folder, version map and run log are in
# step 4d's file. No "required reviewer" rule is set here: see docs/CICD_SETUP.md, "Approval before prod".
log "5/5 ${CI_NAME} configuration"
if [ "$SKIP_CI_CONFIG" = 0 ]; then
  if [ -n "$GH_ENV" ]; then
    gh api -X PUT "repos/${GITHUB_REPO}/environments/${GH_ENV}" >/dev/null && ok "environment ${GH_ENV}"
    gh variable set WIF_PROVIDER        --repo "$GITHUB_REPO" --env "$GH_ENV" --body "$WIF_PROVIDER"
    gh variable set GCP_SERVICE_ACCOUNT --repo "$GITHUB_REPO" --env "$GH_ENV" --body "$SA"
    gh variable set TF_STATE_BUCKET     --repo "$GITHUB_REPO" --env "$GH_ENV" --body "$BUCKET"
    ok "identity + state bucket variables set on ${GH_ENV}"
  else
    gh variable set WIF_PROVIDER        --repo "$GITHUB_REPO" --body "$WIF_PROVIDER"
    gh variable set GCP_SERVICE_ACCOUNT --repo "$GITHUB_REPO" --body "$SA"
    gh variable set TF_STATE_BUCKET     --repo "$GITHUB_REPO" --body "$BUCKET"
    ok "identity + state bucket variables set on the repository"
    for e in qa prod; do gh api -X PUT "repos/${GITHUB_REPO}/environments/${e}" >/dev/null && ok "environment ${e}"; done
  fi
  gh repo edit "$GITHUB_REPO" --default-branch main >/dev/null 2>&1 && ok "default branch main" || true
else
  ok "nothing pushed to GitHub (--skip-ci-config); set these by hand:"
fi

cat <<EOF

Identity GitHub Actions presents (Environment variables${GH_ENV:+ on \`${GH_ENV}\`}):
  WIF_PROVIDER         = ${WIF_PROVIDER}
  GCP_SERVICE_ACCOUNT  = ${SA}
  TF_STATE_BUCKET      = ${BUCKET}   (Terraform state; the bucket also holds the version map)
Everything else about the environment is in Git — commit this (nothing secret inside):
EOF
for f in "${ENV_FILES[@]}"; do echo "  ${f}"; done
echo "  (destination ${PROJECT}, manifests/<env>/, version map gs://${BUCKET}/<env>/version_map, run log ${BQ_DATASET:-off})"
if [ ${#SOURCES[@]} -gt 0 ] && [ ${#TODO_SOURCE[@]} -eq 0 ]; then
  echo "Source-side grants: done on ${SOURCES[*]} (service agent = documentai.editor, ${SA_NAME} = documentai.viewer${BQ_DATASET:+ + BigQuery})."
else
  echo "Still to do by the SOURCE project's owner (IAM admin there), per source this destination imports from — docs/IAM.md:"
  if [ ${#TODO_SOURCE[@]} -gt 0 ]; then
    for c in "${TODO_SOURCE[@]}"; do echo "  $c"; done
  else
    echo "  gcloud projects add-iam-policy-binding <SOURCE> --member=serviceAccount:${DEST_AGENT} --role=roles/documentai.editor"
    echo "  gcloud projects add-iam-policy-binding <SOURCE> --member=serviceAccount:${SA} --role=roles/documentai.viewer"
    [ -n "$BQ_DATASET" ] && echo "  (+ roles/bigquery.jobUser and roles/bigquery.dataEditor for ${SA} where the run-log table lives)"
    echo "  or re-run this script with --source <SOURCE> (repeatable) as someone who has IAM admin on the source."
  fi
fi
