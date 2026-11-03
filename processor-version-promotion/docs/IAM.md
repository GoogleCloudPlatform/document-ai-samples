# Identities and roles

Three identities take part in a promotion through CI. None of them uses a service account key.

| | Identity | Role | On |
|---|---|---|---|
| A | **The CI identity**: GitHub's OIDC token, exchanged through Workload Identity Federation. Principal: `principalSet://iam.googleapis.com/projects/<number>/locations/global/workloadIdentityPools/<pool>/attribute.repository/<owner>/<repo>` | `roles/iam.workloadIdentityUser` | service account B |
| | | `roles/serviceusage.serviceUsageConsumer` | destination project |
| B | **The pipeline service account** `docai-promoter@<destination>.iam.gserviceaccount.com`. Runs Terraform and the scripts. | `roles/documentai.editor`, `roles/browser`, `roles/serviceusage.serviceUsageConsumer` | destination project |
| | | `roles/storage.objectAdmin` | the state bucket `gs://<destination>-tfstate` |
| | | `roles/documentai.viewer` | training project |
| | | `roles/bigquery.jobUser`, `roles/bigquery.dataEditor` (only with the run log) | the project that holds the run log (the training project by default) |
| C | **The destination's Document AI service agent** `service-<destination number>@gcp-sa-prod-dai-core.iam.gserviceaccount.com`. `ImportProcessorVersion` runs as this identity and reads the model out of the training project. | `roles/documentai.editor` | training project |

`bootstrap/setup_cicd.sh` creates B, the pool and the provider, and grants everything above on the
destination project. With `--source <training-project>` it also grants B's and C's roles on the
training project. Without IAM admin there, it prints the exact commands for the project's owner.

## Notes

- **A needs `serviceUsageConsumer`.** The Python client libraries send a quota-project header. Without
  this role they fail with `USER_PROJECT_DENIED` on `iamcredentials.googleapis.com`. Terraform's
  provider doesn't send the header, so only the script would fail.
- **C is created lazily**, on the project's first Document AI call. The setup script creates it up
  front (`services/documentai.googleapis.com:generateServiceIdentity`) so the grant on the training
  project has a member to bind.
- **C's grant can also come from Terraform**: set `source_project_id` in the environment's tfvars and
  `main.tf` creates the binding (`google_project_iam_member.source_docai_editor`). B then needs
  permission to set IAM policy on the training project, which most teams won't give a pipeline. The
  default is therefore a one-time grant by the setup script or the project's owner.
- **Pre-flight checks** in `copy_processor.py` confirm B's access to both projects and C's role on
  the training project before anything changes.
- **People are read-only in qa and prod**, for example `roles/documentai.viewer`. The pull request is
  the only write path.
- **The person who runs the setup script** needs Editor, Project IAM Admin and
  `roles/iam.workloadIdentityPoolAdmin` on the destination project, and IAM admin on the training
  project for `--source`.
- **Local runs** with your own Application Default Credentials need B's roles for your user account.
- **Billing** must be enabled in every destination project. The import works without it; the deploy
  fails with `BILLING_DISABLED`.
