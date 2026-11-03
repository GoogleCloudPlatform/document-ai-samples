# Environments

One file per environment, `environments/<env>.tfvars`. One environment is one destination project.
The file names the destination project, the manifest folder (`manifests/<env>/`), the version map
and the run log. Nothing in it is secret, so it's committed. The Terraform code is the same for every
environment; only this file changes.

Create it in one of two ways:

- `bootstrap/setup_cicd.sh --project <destination-project> --github <owner/repo> --env <env>` writes it
  from the resources it creates (it never overwrites an existing file).
- Or copy `example.tfvars` to `<env>.tfvars` and set the values.

An empty `manifests/<env>/` folder is a valid environment: its plan says "No changes" until the
first manifest is exported into it.

## Adding an environment

1. Create `environments/<env>.tfvars` as above, and commit it with the `manifests/<env>/` folder.
2. On GitHub Actions, add `<env>` to the `matrix.environment` list in `.github/workflows/plan.yml`
   and `.github/workflows/apply.yml`. The order in `apply.yml` is the promotion order.
