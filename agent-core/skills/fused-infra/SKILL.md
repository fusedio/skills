---
name: fused-infra
description: Reference for the infrastructure managed by fused — what resources exist, why each one is needed, and when they are created, updated, or deleted. Covers the AWS backend (IAM, Lambda, ECR, S3) and the local backend (data directories + venvs, see "Local backend infra"). Use when helping users understand, provision, or troubleshoot the resources that back an fused environment.
---

# fused AWS infrastructure

> **Part of the Fused skill set.** This covers the AWS resources only. For install
> and provisioning see **`fused-setup`**; see **`fused-guide`** for the full set.

fused manages a small, fixed set of AWS resources per environment. All resources are scoped to the environment's `function_prefix` (default `openfused-`). Nothing outside that scope is touched.

---

## Resources managed

### IAM role

**Name**: `<prefix>` with trailing `-` stripped (e.g. `openfused-` → `fused`), or overridden with `--role-name` / `role_name` in the env config.

**Why**: Every Lambda function must assume an IAM role to run. fused creates and owns this role so users don't have to wire one up manually.

**What's in the inline policy** (`openfused-default`):

| Statement | Permissions | Scope |
|---|---|---|
| `S3Access` | `GetObject`, `PutObject`, `DeleteObject`, `ListBucket` | All S3 (`arn:aws:s3:::*`) |
| `LambdaSelfInvoke` | `lambda:InvokeFunction` | `arn:aws:lambda:<region>:<account>:function:<prefix>*` |
| `SecretsRead` | `secretsmanager:GetSecretValue` | `arn:aws:secretsmanager:<region>:<account>:secret:<prefix>*` |
| `CloudWatchLogs` | `CreateLogGroup`, `CreateLogStream`, `PutLogEvents` | All (`arn:aws:logs:*:*:*`) |
| `ECRPull` *(only when `docker_image` is set)* | `ecr:GetAuthorizationToken`, `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer` | All (`*`) |

The policy is **re-applied on every `infra apply`**, so it self-heals if manually changed.

**When managed**: created on first `infra apply` (or `env create` without `--no-provision`). Updated any time the policy diverges from the desired state (e.g. adding `docker_image` to an env adds the ECR statement).

---

### Lambda function

**Naming**: one function per environment, `<prefix>container`. Example: `openfused-container`.

**Why**: Lambda execution is container-based — the env's `docker_image` (an ECR image URI, built with `fused infra build-image`) *is* the function's code. Packages are baked into the image (`env update -p <pkg>` + `infra build-image`); fused never pip-installs packages at invocation time.

**Runtime**: the env's `docker_image` ECR URI (`PackageType: Image`).

**Configuration applied on `infra apply`**:
- `Code`: the image URI from `docker_image`
- `Timeout`: value from `lambda_timeout` in the env config (default 300 s)
- `MemorySize`: value from `lambda_memory_mb` (default 1024 MB)
- `EphemeralStorage`: value from `lambda_tmp_storage_mb` (when not the 512 MB default)
- `Architectures`: value from `lambda_architecture` — changing it is a REPLACE (delete + recreate), since architecture cannot be updated on an Image-type function
- `TenancyConfig`: `{"TenantIsolationMode": "PER_TENANT"}` — every compute function fused invokes is created with **AWS Lambda tenant isolation mode**, so each invocation runs in an execution environment dedicated to its tenant id (the caller identity, or a shared placeholder).

`infra plan` compares the live function's image URI, memory size, ephemeral storage, architecture, and tags against the desired state and reports drift (a leftover zip-packaged function from an old install is reported as REPLACE). `infra apply` reconciles them. Tenant isolation is **not** drift-checked: AWS only allows it to be set at function *creation*.

**What's NOT managed**: Lambda functions outside `<prefix>*` are never touched. The deployed **serve** Lambda (behind API Gateway) is intentionally *not* tenant-isolated — API Gateway can't attach a tenant id on invoke; isolation happens on its call into the compute function instead.

---

### ECR repository

**Name**: extracted from the `docker_image` URI (registry host stripped, tag stripped) — e.g. `123.dkr.ecr.us-east-1.amazonaws.com/myapp:latest` → `myapp` — or, before a first image exists, `image_build.repo` (default: the prefix minus the trailing dash).

**Why**: the Lambda function's container image must live in ECR in the same account. fused ensures the repo exists before `docker push`.

**When managed**: `infra apply` creates the repository if missing. `infra build-image` also creates it during the build workflow.

**Teardown**: deleted (with `force=True`, removing all images) when `infra teardown` is run and a `docker_image` is configured.

> **Serve repo:** `infra serve` creates a *separate* ECR repository,
> `<prefix.rstrip('-')>-serve`, holding the dispatcher image (content-tagged).
> It is created on first `infra serve` and removed by `infra teardown`.

---

### S3 cache bucket *(optional — only when `cache_bucket` is set)*

**Name**: auto-derived as `<prefix without trailing dash>-cache` (e.g. `openfused-cache`), or set explicitly with `--cache-bucket` / `--no-cache-bucket`.

**Why**: `fused code run` / `code test` accept `--input-file` (repeatable), which uploads local files into the Lambda execution context. Those files are staged in this bucket as a temporary zip, then downloaded and extracted inside Lambda before user code runs.

**When managed**: `infra apply` creates the bucket if it does not exist. S3 bucket creation is region-aware (us-east-1 does not accept a `LocationConstraint`).

**Lifecycle rules**: `infra apply` also reconciles three openfused-managed expiry rules on the bucket (and `infra plan` reports them as drift when absent):

| Rule ID | Prefix | Expiration | Purpose |
|---|---|---|---|
| `openfused-expire-spill` | `spill/` | 1 day | One-shot large-result spills (caching off) — read once, then garbage |
| `openfused-expire-context` | `context/` | 1 day | Staged `input_files` zips |
| `openfused-gc-results` | `results/` | 30 days | Storage GC backstop for cache entries — **not** the freshness mechanism (that's `cache_max_age` at read time), so keep TTLs under 30d |

Rules are merged idempotently: any customer-defined rule (one whose ID does not start with `openfused-`) is preserved. Requires `s3:GetLifecycleConfiguration` and `s3:PutLifecycleConfiguration`.

**Teardown**: all objects are deleted first, then the bucket itself is deleted when `infra teardown` runs.

**What's NOT managed**: user data buckets (the ones you pass to `files list`, `files get`, etc.) are never created or deleted by fused infra.

---

## Lifecycle

> These operations are CLI commands only (`fused infra plan|apply|build-image|lambda-reset|teardown|serve`, `fused env create`). There are no MCP tool equivalents.

### On `env create` (AWS, default)
1. Config is written to `~/.openfused/envs.json`.
2. `infra apply` runs automatically — provisions the IAM role, the S3 bucket (if `cache_bucket` set), and — when `docker_image` or `image_build` is configured — the ECR repo, the container image (built and pushed during apply if missing from ECR), and the `<prefix>container` Lambda function.

Pass `--no-provision` to skip step 2 (useful when the role already exists or you want to review the plan first).

### On first `fused code run` call
If `infra apply` has not already created it, the `<prefix>container` function is created lazily on the first call from the env's `docker_image` and waited on until `Active` (~15–30 s). With no image configured, the call fails with guidance to run `fused infra build-image` first. Subsequent calls reuse the function.

### `infra plan`
Dry run. Compares current AWS state against desired state and prints a diff. Exits 0 if nothing to change, 1 if there is drift. Useful in CI.

### `infra apply`
Reconciles all managed resources to the desired state. Safe to run repeatedly — idempotent.

### `infra teardown`
Deletes Lambda functions (all matching `<prefix>*`), the IAM role and its inline policy, the CodeBuild project and its service role (if the env uses the `codebuild` builder), the ECR repository (if `docker_image` set), and the cache bucket (if set). Prompts for confirmation unless `--yes` is passed.

**Does NOT delete**: user S3 buckets, Secrets Manager secrets.

### `infra build-image`
Builds a Docker image and pushes it to ECR, then writes the resulting digest URI back into the resolved env's `docker_image` field. The next `infra apply` will update the `<prefix>container` Lambda function to use it.

By default the build runs remotely in **AWS CodeBuild** — no Docker daemon needed on the host. Pass `--builder local` (or set the env's `builder` to `local`) to fall back to a host `docker build` instead. CodeBuild builds in your own account, requires a cache bucket (the build source is uploaded there under `codebuild-source/`), and pushes via a service role whose ECR push is **scoped to just this env's repo** (the broad Lambda-execution ECR-pull grant stays `*`). The CodeBuild project (`<prefix>build`) + role are provisioned on demand and also appear in `infra plan`/`infra apply` and are removed by `infra teardown`. It accepts a user Dockerfile via `--context-dir`/`--dockerfile`. With no cache bucket (a deliberate `--no-cache-bucket`), the CodeBuild build fails fast with guidance to set one or pass `--builder local`. Limitation: concurrent same-tag builds aren't supported (digest resolved by mutable tag).

---

## When to run `infra apply`

| Situation | Action needed |
|---|---|
| New environment | `env create` does it automatically |
| Changed `lambda_timeout` in env config | `infra apply` |
| Changed `docker_image` (e.g. after `build-image`) | `infra apply` |
| fused handler code updated (new release) | `infra build-image` (the handler files are baked into the image), then `infra apply` |
| IAM policy manually modified in AWS console | `infra apply` — self-heals |
| `docker_image` added to an existing env | `infra apply` — adds ECR pull permission to IAM role |

---

## Permissions required to run infra commands

The AWS credentials used to run `infra apply` / `teardown` must have:
- `iam:CreateRole`, `iam:GetRole`, `iam:PutRolePolicy`, `iam:DeleteRole`, `iam:DeleteRolePolicy`, `iam:GetRolePolicy`
- `lambda:CreateFunction`, `lambda:GetFunction`, `lambda:ListFunctions`, `lambda:UpdateFunctionCode`, `lambda:UpdateFunctionConfiguration`, `lambda:DeleteFunction`, `lambda:TagResource`
- `ecr:DescribeRepositories`, `ecr:CreateRepository`, `ecr:DeleteRepository`
- `s3:HeadBucket`, `s3:CreateBucket`, `s3:DeleteBucket`, `s3:ListBucket`, `s3:DeleteObject`, `s3:GetLifecycleConfiguration`, `s3:PutLifecycleConfiguration` *(if cache_bucket set)*
- `tag:GetResources` *(Resource Groups Tagging API — discovers deployed resources by their `fused:*` tags)*
- `sts:GetCallerIdentity`

---

## Local backend infra

For a **local environment** (`backend: "local"`), "infra" is the
data/secrets/venvs directories and the cached venv holding the env's `packages`,
managed by `LocalPythonInfraManager`. No cloud resources; the only
prerequisites are a Python interpreter and uv (project venvs are uv-managed). The
same `fused infra` CLI commands dispatch to it.

| What's managed | Detail |
|---|---|
| Data directory | `local_path` (default `~/.openfused/data`) — created on `apply`. |
| Secrets directory | the parent dir of `secrets_file` — created on `apply`. |
| Venvs directory | `venvs_path` (default `~/.openfused/venvs`) — created on `apply`. |

- **`infra plan`** — reports missing dirs; exits 1 on drift.
- **`infra apply`** — creates the dirs and the packages venv. Idempotent.
- **`infra build-image`** — **errors** for local envs (no image; run `infra apply`).
- **`infra teardown`** — removes the venvs dir (always — venvs are a reproducible
  cache) and (destructive) `local_path`. Background `code serve` endpoints survive;
  they are detached host processes — stop them by killing the process (Ctrl-C, or
  `kill <pid>`).
- **`infra lambda-reset`** — clears the in-process venv ready-cache; nothing is
  deleted from disk.
