# CI/CD with GitHub Actions

The workflows in `.github/workflows/` turn a promotion into a pull request: plan on the pull request,
apply on merge. They run from the repository root, so use this folder as the root of your repository.

| Workflow | Trigger | What it does |
|---|---|---|
| `plan.yml` | a pull request that touches `manifests/`, `environments/`, `schemas/`, `scripts/` or `*.tf` | `terraform plan` per environment, posted on the pull request as a comment. Nothing is applied. |
| `apply.yml` | merge to `main` (or *Run workflow*) | `terraform apply` for qa, then prod. Each processor's check results and the default switch are copied onto the run's summary page; the full log is kept as an artifact. |
| `export.yml` | *Run workflow* in the Actions tab | runs `scripts/export_processor.py --open-pr`: writes the manifest and the schema file and opens the promotion pull request. |

## One-time setup, per destination project

```bash
./bootstrap/setup_cicd.sh --project my-qa-project   --github <owner>/<repo> --env qa   --source my-training-project
./bootstrap/setup_cicd.sh --project my-prod-project --github <owner>/<repo> --env prod --source my-training-project
```

For each destination project the script:

1. checks billing and enables the APIs;
2. creates the pipeline service account `docai-promoter` and grants its roles ([IAM.md](IAM.md));
3. creates a versioned state bucket, `gs://<project>-tfstate`, which also holds the version map;
4. creates a Workload Identity pool and a GitHub OIDC provider that accepts tokens from your
   repository only, and lets that repository impersonate the service account;
5. with `--source`, grants the roles the import needs on the training project;
6. writes `environments/<env>.tfvars` (commit it);
7. creates the GitHub Environment `<env>` and sets three variables on it with the `gh` CLI:

| Variable | Value |
|---|---|
| `WIF_PROVIDER` | `projects/<number>/locations/global/workloadIdentityPools/cicd/providers/github` |
| `GCP_SERVICE_ACCOUNT` | `docai-promoter@<project>.iam.gserviceaccount.com` |
| `TF_STATE_BUCKET` | `<project>-tfstate` |

The script is idempotent; re-run it after a partial failure. Use `--skip-ci-config` to print the
variables instead of setting them, and `--no-bq` if you don't want the BigQuery run log.

For `export.yml`, add a fine-grained token with contents and pull-request write access as the
repository secret `GH_PR_TOKEN`. A pull request opened with the default `GITHUB_TOKEN` doesn't trigger
other workflows, so `plan.yml` would stay silent.

## Approval before prod

The pull-request review approves the release for every environment. To also require a person to
approve the prod apply after qa succeeds, add a required reviewer to the `prod` GitHub Environment.

`plan.yml` binds the same Environment to read its variables, so the prod plan on each pull request
then waits for that approval too. If you don't want that, create a second Environment for the plan
job (for example `prod-plan`) with the same three variables, and point `plan.yml` at it.

## The first run

Open a pull request that adds a manifest under `manifests/qa/`. The plan comment should show the
processor to create and one `terraform_data.promote` to add. `Error acquiring the state lock` or
`USER_PROJECT_DENIED` mean the setup above is incomplete ([IAM.md](IAM.md)).

Already have a destination processor? Adopt it instead of creating a second one: add
`existing_processor_id: "<id>"` to its manifest. The plan shows `will be imported`. After the first
successful apply, delete the line.

## Failures and re-runs

- A failed check exits with code 3. The apply fails, the run turns red, and the processor keeps its
  current default. The next apply runs the copy and the checks again.
- Terraform runs up to ten processors in parallel. If one fails, the others finish and the unstarted
  ones run on the next apply. Re-run `apply.yml` with *Run workflow*.
- `force_reconcile = true` in an environment's tfvars re-runs every processor on the next apply, even
  if nothing changed in Git. Set it back to `false` afterwards.
