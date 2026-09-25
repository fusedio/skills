---
name: fused-setup
description: Step-by-step guide for installing and setting up fused for the first time, including AWS credential checks, detecting an existing installation, provisioning infrastructure, and verifying the setup. Use when a user asks how to install, configure, or get started with openfused.
---

# Setting up fused

> **Part of the Fused skill set.** This covers install + provisioning only. Once
> set up, see **`fused-guide`** to route to the skill for the actual task
> (`fused-projects`, `fused-execute`, etc.).

## Overview

Setup has four phases:

1. **Pre-flight** — verify AWS credentials and check for an existing install
2. **Install** — add the package
3. **Provision** — create an environment and AWS resources
4. **Verify** — confirm everything works before doing real work

Never skip phase 1. Running `infra apply` or `env create` against the wrong account is hard to reverse.

---

## Phase 1 — Pre-flight checks

### 1a. Verify AWS credentials

```sh
aws sts get-caller-identity
```

Expected output:
```json
{
    "UserId": "AIDAQ...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/yourname"
}
```

**If this fails**: credentials are missing or expired. Fix before continuing:
- AWS SSO: `aws sso login --profile <profile>`
- Static credentials: ensure `~/.aws/credentials` or `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` are set
- Instance/container role: verify the metadata endpoint is accessible

**Confirm the Account ID is correct** before proceeding. Provisioning into the wrong account will leave orphaned resources.

### 1b. Check for an existing fused installation

```sh
fused env list
```

- If the command is not found: fused is not installed → proceed to Phase 2.
- If it runs but shows no environments: fused is installed but not configured → skip to Phase 3.
- If it shows environments: **read Phase 1c before touching anything.**

### 1c. Existing installation — understand what's already there

If environments are listed, check the current AWS state before making changes:

```sh
fused infra plan
```

Read the output carefully:
- `ok` — the resource already exists and matches desired state. No action needed.
- `CREATE` — resource will be added on `infra apply`.
- `UPDATE` — resource exists but has drifted; `infra apply` will fix it.
- `DELETE` — resource will be removed (only appears during teardown flows).

**Do not run `infra apply` or `infra teardown` without reviewing this output first.**

If you need full config details for a specific environment:
```sh
fused env show <name>      # JSON dump of stored config
fused env show             # config for the resolved environment
```

---

## Phase 2 — Install

**Working inside the fused repo** (development):
```sh
uv sync --all-extras
uv run fused --version   # prefix all fused commands with `uv run`
```

**Installing into another project or environment**:
```sh
# as a CLI tool (pick the extras you need, see below)
uv tool install 'fused[aws]'

# or as a project dependency
uv add 'fused[aws]'
pip install 'fused[aws]'
```

### Which extras you need

A bare `fused` install gives you the CLI and the **local** backend. Everything
else is opt-in:

| Extra | Pulls in | Needed for |
|---|---|---|
| *(none)* | CLI, local backend, `fused app serve` | Local-backend work; the `fused` (hosted) backend |
| `data` | pyarrow, pandas, numpy | `fused files schema`; calling `fused.run()` on a UDF that returns a DataFrame |
| `aws` | boto3 + `data` | The **AWS backend** (`--backend aws`): Lambda execution, S3, Secrets Manager, `infra …`, `share …` on AWS |
| `verify` | anthropic, ty | `fused code verify --spec` (the LLM spec review; without it, `--spec` yields a `spec/review-error` warning) and the type-checker scanner |
| `local` | keyrings.alt | Local-backend secrets on Linux/WSL hosts with no OS keychain (stores them unencrypted — dev only) |
| `geo` | geopandas, shapely, rasterio, xarray, … + `data` | The vendored workbench SDK's geo helpers on the host. `vector`, `raster` and `batch` still work as aliases; prefer `geo` |
| `workbench` | selenium, fastmcp | The `fused workbench` CLI's JSON-UI and MCP commands |
| `all` | every extra except `local` | Everything, without the plaintext secrets fallback |

A typical AWS user installs `'fused[aws,verify]'`; a local-only user needs no extras
(add `local` on a keychain-less Linux box).

> **Host extras are not sandbox packages.** What your code can import inside
> `fused code run` comes from the environment's container image (AWS:
> `env update -p <pkg>` + `infra build-image`) or the project's venv (local:
> `fused project add-dep`), never from the extras installed on the host.

> All `fused` commands below assume the package is on `PATH`. If working inside this repo, prefix every `fused ...` command with `uv run`: e.g. `uv run fused env list`.

> **CLI only.** The `fused` package is a CLI plus the data plane. It no longer
> ships an MCP server (a bare `fused` prints help) or a widget viewer, and needs no
> Node. The only MCP surface is `fused app serve <dir>`, which serves an app
> folder's `mcp.toml` tools over stdio (see fused-cli).

---

## Phase 3 — Create an environment

### Choosing a backend

You do **not** need a cloud account to get started. Pick by what's available:

| Backend | `--backend` | Needs | Best for |
|---|---|---|---|
| **AWS** | `aws` | AWS credentials, plus Docker to build the Lambda container image (or `--builder codebuild` to build remotely without it) | Production and horizontal scale |
| **Local** | `local` | nothing — host venvs via uv/pip, no cloud | The fastest start; local dev/CI. No isolation boundary: code runs directly on the host |
| **Fused** | `fused` | A Fused-managed fused environment + an API key (guided onboarding flow) | Running code on a remote, managed fused that Fused provisions and operates — the local side provisions nothing |

AWS Lambda execution is **container-only**: packages (`duckdb`, `polars`, `h3`, etc.) are baked into an ECR image via `fused infra build-image`, and that image is the Lambda function's code. There is no runtime fallback — until an image is built and configured, `fused code run` fails with a clear error telling you to run `infra build-image`. Per-call requirements are never pip-installed at invocation time.

### AWS environment

Before running this, confirm the AWS account from Phase 1a is the right target.

```sh
# 1. Create the environment (provisions IAM role, S3 cache bucket, ECR repo)
fused env create prod --backend aws --prefix myapp- --no-provision
fused infra plan    # review what will be created

# 2. Build the Docker image and push to ECR
fused infra build-image

# 3. Apply — creates IAM role, S3 bucket, ECR repo, and the Lambda function
fused infra apply
```

The `image_build` config in `~/.openfused/envs.json` controls which Python packages and system deps go into the image. Edit it before building:

```json
"image_build": {
  "python_version": "3.12",
  "packages": ["duckdb", "polars", "h3", "pyarrow"],
  "system_deps": [],
  "platform": "linux/amd64"
}
```

**Lambda creation:** a single Lambda function (`<prefix>container`) is created during `infra apply` once a `docker_image` or `image_build` is configured. The first `fused code run` call hits an already-existing function. Without an image, `infra apply` provisions only the IAM role and S3 buckets, and execution errors until you run `infra build-image`.

### Local environment (no AWS required — good for testing and development)

```sh
fused env create dev --backend local
```

No AWS — code runs on the user's own machine, in a subprocess. Scaffolds
`~/.openfused/envs/dev/data`. Bare (project-less) calls use a stdlib-only venv
created lazily on first use.
Third-party dependencies belong to a project's `scripts/pyproject.toml` (managed
with `fused project add-dep <project> <pkg>`) — not to the environment itself.

```sh
# Provision dirs up front (otherwise lazy on first call)
fused infra apply
```

Cloud credentials need no configuration: the execution subprocess **inherits the
host environment** directly, so whatever works in the user's shell works in
executed code. Note there is **no isolation boundary** — code runs directly on
the host as the invoking user. AWS-only image-build flags (`--system-dep`,
`--python-version`, `--image-platform`, `--image-repo`, `--image-tag`,
`--builder`, `--dockerfile`, `--context-dir`) are rejected on a local env.

### Choosing a prefix

The prefix (`--prefix`) scopes all AWS resources: IAM role, Lambda functions, Secrets Manager secrets, and the cache S3 bucket. Pick something unique per project and account.

| Prefix | IAM role | Cache bucket |
|---|---|---|
| `openfused-` (default) | `fused` | `openfused-cache` |
| `myapp-` | `myapp` | `myapp-cache` |
| `myapp-staging-` | `myapp-staging` | `myapp-staging-cache` |

S3 bucket names are globally unique — if `openfused-cache` is taken in your account region, choose a custom prefix.

### Permissions required

The AWS credentials used to provision must have:
- `iam:CreateRole`, `iam:GetRole`, `iam:PutRolePolicy`, `iam:GetRolePolicy`
- `lambda:CreateFunction`, `lambda:GetFunction`, `lambda:ListFunctions`
- `s3:HeadBucket`, `s3:CreateBucket`
- `sts:GetCallerIdentity`

See the `fused-infra` skill for the complete permissions list.

---

## Phase 4 — Verify

### 4a. Confirm no infrastructure drift (AWS only)

```sh
fused infra plan
```

All lines should show `ok`. If any show `CREATE` or `UPDATE`, run `infra apply` to converge. For local environments, `infra plan` instead reports the data/secrets/venvs directories and the packages venv.

### 4b. Run a smoke test

```sh
fused code run -c "result = 1 + 1"
```

Expected output:
```
result: 2
```

**AWS:** The function already exists after `infra apply` — the first call pays only the container init cost, not function creation. (If the function is missing, it is created lazily from the configured image, ~15–30 s; with no image configured the call errors and points at `infra build-image`.)

**Local:** The first run creates the packages venv via uv/pip if `infra apply` hasn't already done so. Subsequent runs with the same package set reuse it. Cold start is typically under a few seconds.

### 4c. Confirm environment selection

```sh
fused env list           # lists all envs with their backend
fused env show <name>    # full config for a named env
```

With a **single environment**, commands resolve it automatically (sole-env auto).
With **multiple environments**, pass `--env <name>` or pin a project:
```sh
fused project set my-project --env <name>   # writes default_env to openfused.toml
```
`OPENFUSED_ENV=<name>` is a process-wide override that beats the manifest pin.

---

## Common issues

### `fused infra plan` shows CREATE after `env create`

This is expected when `--no-provision` was used. Run `fused infra apply` to provision.

### IAM role already exists from a previous install

`infra apply` is idempotent — it updates the policy to match the desired state and does not error on an existing role.

If you want to reuse an existing role rather than let fused manage it:
```sh
fused env create prod --backend aws --role-arn arn:aws:iam::123456789012:role/my-existing-role --no-provision
```

### S3 bucket name conflict

If bucket creation fails with a naming conflict, supply an explicit name:
```sh
fused env create prod --backend aws --cache-bucket my-unique-bucket-name
# or suppress the cache bucket entirely:
fused env create prod --backend aws --no-cache-bucket
```

### First `fused code run` call times out

Lambda function creation takes ~15–30 s. Increase the client timeout or retry once. The function will be active on subsequent calls.

### `infra build-image` fails because Docker is unavailable

Image builds use **AWS CodeBuild by default** (no local Docker). You'd only hit a Docker error if you opted into the `local` builder (`--builder local`), which runs `docker build` on the host. Either drop `--builder local` to build remotely in CodeBuild (the default; requires the env's cache bucket), or install Docker (https://docs.docker.com/get-docker/) and start the daemon to keep building locally.

### `uv` not found on the local backend

Local project venvs are uv-managed (`fused project new`, `project add-dep`,
`code run --project`). Install uv (https://docs.astral.sh/uv/getting-started/installation/)
and make sure it is on `PATH`.

---

## Teardown

**Always check `infra plan` before teardown to understand what will be deleted.**

```sh
fused infra plan         # review current state first
fused infra teardown     # prompts for confirmation
```

`infra teardown` removes:
- Lambda functions matching `<prefix>*`
- The managed IAM role and its inline policy
- The ECR repository (if `docker_image` is configured)
- The S3 cache bucket (if configured, after emptying it)

`infra teardown` does **not** remove:
- User data S3 buckets
- Secrets Manager secrets
- The environment config in `~/.openfused/envs.json`

To also remove the env config:
```sh
fused env delete prod --yes    # config only; does not touch AWS
```

**Always confirm with the user before running `infra teardown`.** It deletes Lambda functions and the IAM role. Recreating them takes ~30 s, but:

- Any IAM policies added to the role outside of fused will be lost — fused only restores its own managed inline policy.
- If the role was granted access to external resources (S3 bucket policies, KMS key policies, cross-account trusts, SQS/SNS resource policies, EC2 instance profiles), those associations reference the role's internal unique ID. Deleting the role breaks those associations — even if the role is recreated with the same name and ARN, the new role has a different identity and will not inherit the external grants.
