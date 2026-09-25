---
name: fused-cli
description: Reference for the fused CLI — environment management, file storage, secrets, code execution, and infrastructure commands. Use when writing or explaining shell commands that invoke `fused`, or when helping users set up, switch between, or provision environments. If the commands are part of building or running a project, load `fused-projects` first for the end-to-end model.
---

# fused CLI reference

> **Part of the Fused skill set — don't work from it alone.** This is the command
> reference. For the workflow that decides *which* commands to run, load
> **`fused-projects`** (project lifecycle) or **`fused-execute`** (running code).
> See **`fused-guide`** for the full set.

Check the installed version with `fused --version` (useful for confirming an install before configuring anything).

## Environment selection

Every command targets a specific backend. Two ways to select it:

**Named environment (recommended)** — stored config in `~/.openfused/envs.json`:
```sh
fused --env prod files list
fused --env staging secrets list
```
`--env` can be omitted when the environment is resolved by project manifest or sole-env auto-selection (see resolution rules below).

**Legacy inline selection** — reads config from environment variables:
```sh
fused --backend aws files list        # reads OPENFUSED_* env vars
fused --backend local files list      # host venvs (uv/pip)
fused --backend fused files list      # Fused's managed fused
```

`--env` always wins over `--backend`. `OPENFUSED_ENV` is the env-var form of `--env`.

**Environment resolution order** (first match wins):
1. `--env` flag or `OPENFUSED_ENV` → explicit override (beats everything)
2. Inside a project with `[project].default_env` in `openfused.toml` → manifest pin
3. The global default environment (`fused env default NAME` sets it; `fused env default` prints it)
4. Exactly one named environment exists → sole-env auto-select
5. Multiple environments, no pin and no default → most commands pick deterministically (`local` if it exists, else the first name alphabetically); `infra` and deploy commands refuse and ask you to set `default_env` (`fused project set <project> --env <name>`), set a default, or pass `--env`
6. No environments → error: run `fused env create`

### Logging

Host logs (`openfused.*` loggers) go to stderr with a timestamp + level + logger-name
format. Set verbosity with `OPENFUSED_LOG_LEVEL` (default `INFO`; accepts `DEBUG`,
`INFO`, `WARNING`, `ERROR`, `CRITICAL`). Use `DEBUG` to surface Lambda cache hits and
cold-start/digest-resolution details when troubleshooting.

```sh
OPENFUSED_LOG_LEVEL=DEBUG fused --env prod code run --file job.py
```

---

## Environment management (`env`)

Named environments bundle all backend config into a named entry in `~/.openfused/envs.json`.

### Create

```sh
# AWS — provisions IAM role + Lambda automatically
fused env create prod --backend aws --prefix myapp- --region us-east-1

# AWS — skip provisioning (config only)
fused env create staging --backend aws --prefix myapp-staging- --no-provision

# Local — bare stdlib venv; scaffolds ~/.openfused/envs/dev/data automatically
fused env create dev --backend local
```

AWS `env create` runs `infra apply` automatically unless `--no-provision` is given. Pass `--no-provision` when the IAM role / Lambda already exist or when you want to review the plan first.

### List and inspect

```sh
fused env list            # all envs with their backend
fused env show prod       # JSON dump of config
fused env show            # config for the resolved environment
```

To pin an environment to a project (the recommended way to avoid per-command `--env`):
```sh
fused project set my-project --env prod   # validates env exists, writes default_env
fused project set my-project --clear-env  # remove the pin
```

### Update fields

```sh
fused env update prod --region us-east-1
fused env update prod --prefix newprefix- --lambda-timeout 600
fused env update prod --audit-bucket my-audit-bucket   # add/change audit bucket
fused env update prod --no-audit-bucket                # remove audit bucket
fused env update prod -p pandas -p duckdb   # set packages (AWS only: baked into the container image)
```

`env update` accepts all the same flags as `env create` (patch semantics — only specified fields change). Use `--no-cache-bucket` / `--no-audit-bucket` to clear a bucket field.

### Delete

```sh
fused env delete staging --yes   # removes config only; does NOT teardown AWS resources
```

### Full option reference for `env create`

| Option | Default | Notes |
|---|---|---|
| `--backend` | `aws` | `aws` (Lambda), `local` (host bare venv), or `fused` (Fused cloud). |
| `--region` | `us-west-2` | AWS region |
| `--prefix` | `openfused-` | Lambda function name prefix |
| `--role-arn` | — | Use an existing IAM role instead of creating one |
| `--role-name` | derived | Override the managed IAM role name |
| `--lambda-timeout` | `300` | Execution timeout in seconds |
| `--lambda-memory-mb` | `1024` | Lambda memory (MB). **AWS only.** |
| `--lambda-tmp-storage-mb` | `512` | Lambda `/tmp` ephemeral storage (MB). **AWS only.** |
| `--lambda-architecture` | `x86_64` | Lambda CPU architecture (`x86_64` or `arm64`). **AWS only.** |
| `--lambda-externally-managed` | off | Don't auto-manage the execution Lambda. **AWS only.** Skips the `GetFunction` existence check + `CreateFunction` at execute time (invokes it by name) and skips planning/applying it in `infra plan`/`apply`. Use when the Lambda lifecycle is managed separately (e.g. external IaC). Orthogonal to `--role-arn`, which only short-circuits the IAM role. On `env update`, toggle with `--lambda-externally-managed` / `--no-lambda-externally-managed`. |
| `--docker-image` | — | ECR image URI for the Lambda function. Normally set automatically by `infra build-image`; pass it only to register a pre-built image. |
| `--cache-bucket` | auto-derived | S3 bucket for `--input-file` staging, published share artifacts, and CodeBuild sources. Auto-named `<prefix>-cache` by default |
| `--no-cache-bucket` | off | Disable the cache bucket for this env |
| `--audit-bucket` | — | S3 bucket for WORM audit logs. Must have Object Lock enabled; `infra apply` creates it. |
| `--require-spec` | off | Still accepted and stored, but has **no effect**: executions are not verified (see "Verify settings" below). |
| `-p / --package` | — | Pip package to pre-install (repeatable). **AWS only** — baked into the Lambda container image (`image_build.packages`). Errors if passed to a local env. |
| `--system-dep` | — | System package via `dnf` (repeatable). **AWS only** — errors if passed to a local env. |
| `--python-version` | `3.12` | Python version for the container image. **AWS only** — errors if passed to a local env. |
| `--image-platform` | `linux/amd64` | Docker build platform for the container image. **AWS only** — errors if passed to a local env. |
| `--image-repo` | derived from prefix | ECR repository name. **AWS only** — errors if passed to a local env. |
| `--image-tag` | `latest` | Tag for the container image. **AWS only** — errors if passed to a local env. |
| `--builder` | `codebuild` | Image builder. **AWS only** — `codebuild` (default; remote AWS CodeBuild, no local Docker; uses the cache bucket) or `local` (docker build on host). Errors if passed to a local env. |
| `--dockerfile` | — | Path to a user Dockerfile within `--context-dir` (requires `--context-dir`). **AWS only.** |
| `--context-dir` | — | User build-context directory to build instead of the generated Dockerfile. **AWS only.** |
| `--local-path` | `~/.openfused/envs/<name>/data` | Local data directory (**local only**) |
| `--secrets-file` | `~/.openfused/envs/<name>/secrets.json` | Keychain account key identifying the per-env secrets store (**local only**; no file is written) |
| `--no-provision` | off | Skip `infra apply` on AWS |

### Fused (managed-openfused) backend — `--backend fused`

It runs code on **Fused's hosted, managed** environment over its data-plane endpoint. The local side provisions nothing and runs no code itself. `infra` commands are not supported on Fused (Fused operates the runtime). Create an env with `--backend fused`:

| Option | Default | Purpose |
|---|---|---|
| `--tier` | `prod` | Service tier selecting the base URL (`prod`/`staging`/`unstable`). |
| `--mcp-base-url` | — | Explicit data-plane base URL override (dev/self-host). |
| `--fused-org` / `--fused-env-id` | — | Org + environment (UUID or slug) for the scoped URL; set **together**. Omit both to use the bare endpoint with an env-bound key. |
| `--api-key-secret` | — | Name in fused's local secrets store holding the `ofs_` API key. |

```bash
fused env create fused-prod --backend fused --tier prod \
  --fused-org acme --fused-env-id default --api-key-secret fused/prod-key
```

The API key is resolved (first hit wins) from `--api-key-secret` (local secrets store) → `FUSED_API_KEY` → `FUSED_JWT` (scoped URL only). Storage is read + presign only (`files list` / `files get`); writes and secrets are not exposed by the managed surface and raise a clear error.

#### Guided onboarding — the `fused cloud` group

Instead of hand-building the env above, the `fused cloud` group runs the control-plane flow (login → find org/env → wait ready → mint an API key → store it → create the env). Auth0 config defaults to Fused's tenant + the `openfused-server-api` audience; override with `FUSED_CLOUD_AUTH0_DOMAIN` / `FUSED_CLOUD_AUTH0_CLIENT_ID` / `FUSED_CLOUD_AUTH0_AUDIENCE`.

```bash
fused cloud login [--no-browser]            # Auth0 PKCE; caches a control-plane JWT
fused cloud redeem [CODE] [--tier prod]     # redeem a beta invite: admit + create your org + env
                                            #   omit CODE and it prompts (keeps it out of shell history)
fused cloud orgs [--tier prod]              # list your orgs + envs and their provision_state
fused cloud setup [--tier prod] \           # the one-shot guided flow:
  [--beta-code CODE] \                          #   (optional) redeem a beta invite first, then
  [--org O --env E] [--env-name NAME]           #   pick org/env (auto if you have one), wait ready,
                                                #   mint a key, store it, create the `fused` env
fused cloud key create --org O --env E      # mint + store a key for an existing managed env
fused cloud key revoke --org O --id K       # revoke a data-plane key by id
fused cloud logout [--no-browser]           # delete the cached control-plane JWT
fused cloud logout --env NAME               # ALSO delete that env's stored data-plane key (full logout)
```

`setup` stores the minted key in the local secrets store (e.g. `fused/<env-name>-key`) and writes a `FusedCloudEnvironmentConfig` referencing it — never the raw key in `envs.json`. The fused env name defaults to `fused` for the canonical `default` managed env (else `fused-<env>`).

Token resolution at request time (first hit wins): **`FUSED_API_KEY`** env var (an explicit override) → the stored **`api_key_secret`** → **`FUSED_JWT`** (scoped-URL only). A configured-but-absent secret falls through rather than failing. **Logging out:** `fused cloud logout` clears the control-plane JWT; add `--env NAME` to also delete that environment's stored data-plane key (then `fused key revoke` to revoke it server-side).

Tune a managed env after creation with `env update <name>` — the managed-fused fields `--tier`, `--mcp-base-url`, `--fused-org`, `--fused-env-id`, and `--api-key-secret` are accepted (mirroring `env create --backend fused`). `infra` commands are not applicable (Fused operates the runtime) and report that posture.

If you have a **beta invite code**, redeem it during the beta gate either as a standalone step (`fused cloud redeem`, after `login`) or folded into setup (`fused cloud setup --beta-code CODE`). Redeeming admits your account and creates a personal org with a `default` environment, which setup then waits on and wires up. The code is single-use; an invalid or already-redeemed code raises a clear error. Prefer the standalone form with the code omitted — it prompts without echo, so the code stays out of `ps` and your shell history; the same applies to `fused cloud accept [TOKEN]`, the sibling command for joining an org you were invited to.

### Verify settings (`--verify`, `--require-spec`, `--audit-bucket`) — not enforced

`env create` / `env update` still accept `--verify JSON`, `--require-spec` and
`--audit-bucket` and store them in the environment, but **no command runs the
verify pipeline automatically**: `code run` and `code test` execute with no pre-
or post-execution scan, no type check, no spec requirement and no output
firewall. `verify.enabled`, `typecheck`, `typecheck_docker`, `block_on_warn`,
`expectations` and `require_spec` have no effect on execution.

The only verify fields still read are by the explicit `fused code verify` command:
`rules` (a list of `{"rule_id", "severity", "enabled"}` overrides) and the OSV
endpoint used by the dependency scan. See the **fused-verify** skill.

---

## Projects (`project`)

Projects are versioned, deployable collections of UDFs. The on-disk model is: **workspace ⊃ project ⊃ UDF**. All project commands implicitly target the `default` workspace at `~/.openfused/workspaces/default/` (override with `OPENFUSED_WORKSPACES_DIR`).

The first `project new` call auto-creates the default workspace (git init + installs the openfused-managed v6 pre-commit hook). The hook blocks manual commits that touch a UDF's `spec.md` without its `main.py` or vice versa. Use `git commit --no-verify` to bypass it when needed.

### Create a project

```sh
fused project new taxi-pipeline
# Created project 'taxi-pipeline' at ~/.openfused/workspaces/default/taxi-pipeline
```

| Argument | Notes |
|---|---|
| `NAME` | Project name; must match `^[a-z][a-z0-9]*([-_][a-z0-9]+)*$`, max 64 chars |

### List projects

```sh
fused project list
```

Prints all project names in the default workspace, sorted. Prints a help message when none exist yet.

### Add dependencies to a project

```sh
fused project add-dep taxi-pipeline duckdb pandas        # runtime deps
fused project add-dep taxi-pipeline pytest coverage --dev # dev deps (for `code test`)
```

Runs `uv add [--dev] <packages>` then `uv sync` inside the project's `scripts/`
dir in one step, so the lockfile and the installed venv stay in step — avoiding
the stale-venv warning (and silent cache-disable) a bare `uv add` would leave
behind. Never hard-fails on tooling problems (missing `uv`, `OPENFUSED_LOCAL_INSTALLER=pip`,
non-zero exit) — it prints a guided `Warning:` instead. Errors only on an unknown project.

### Show a project

```sh
fused project show taxi-pipeline
```

With `NAME` omitted, uses the resolved project (`OPENFUSED_PROJECT` → `openfused.toml` walk-up from cwd). Prints the project's **context packet** as JSON:

- `project` — `name`, `root`, `description`, `registered`, `source`
- `contract` — the project's `SKILL.md`
- `references` — the notes under `references/`
- `udf_scripts` — the UDFs under `scripts/`
- `environment` — `default_env`, `resolved_env`, `resolved_from`, `backend`, `error`, `warnings`

`project show` is **read-only**: it does not re-sync `openfused.toml`. Exits with an error when the project does not exist.

### Migrate / repair a project's layout (`project migrate`)

```sh
fused project migrate taxi-pipeline
```

Moves legacy root-level UDF folders into `scripts/<name>/` (committing the move),
then **re-syncs the manifest from disk**: discovers UDF folders under `scripts/`,
drops `[udfs.*]` entries with no folder, and preserves user-set fields
(`description`/`auth`/`cache_max_age`, unknown keys, TOML comments). It is the only
CLI command that re-syncs the manifest. Use it to repair a manifest that no longer
validates — for example a leftover `kind = "json"` UDF entry, which `doctor`
reports as `manifest-unreadable`. When nothing was moved, the re-synced
`openfused.toml` is left uncommitted; commit it yourself.

### Delete a project

```sh
fused project delete taxi-pipeline
```

Removes a project from the default workspace: `git rm -rf -- <name>` followed by
a `--no-verify` commit, then cleans gitignored/untracked residue (`scripts/.venv`,
`__pycache__`). An underscore-prefixed name fails slug validation ("Invalid
slug"). Prints JSON `{name, deleted, root}` on success.

### Naming rules

Project and UDF names are **lowercase slugs**: `^[a-z][a-z0-9]*([-_][a-z0-9]+)*$`, max 64 chars. Both `-` and `_` are accepted as segment separators, so snake_case UDF names like `list_comments` are valid. Lowercase-only prevents case-collision bugs on case-insensitive filesystems and in S3 key segments.

### Workspace layout

```
~/.openfused/workspaces/default/    # the default workspace (one git repo)
├── .git/                           # openfused-managed pre-commit hook installed here
├── taxi-pipeline/                  # a project = one folder
│   ├── openfused.toml              # manifest (re-synced from disk by `project migrate`)
│   ├── SKILL.md                    # project contract (agents read this for context)
│   ├── assets/                     # static project assets
│   ├── references/                 # dataset notes + findings (one file per topic)
│   └── scripts/
│       ├── pyproject.toml          # uv-managed Python deps (note: uv's [project] table, not fused's)
│       ├── tests/                  # project-level pytest suites
│       ├── taxi-analysis/          # a UDF, kind: py
│       │   ├── main.py
│       │   ├── spec.md
│       │   └── test_main.py
│       └── clean-trips/            # another UDF
│           ├── main.py
│           └── spec.md
└── sales-app/
```

A UDF is a folder under `scripts/` that contains `main.py` (kind `py`, the only
kind). `main.json` has no special meaning — it is an ordinary file, and a folder
holding only `main.json` is not a UDF. Dot-prefixed and underscore-prefixed
directories are skipped.

### Authoring UDFs (agent-authored)

There is no `udf generate` or `project regenerate` command. UDFs are authored by the driving agent:

1. Write `scripts/<name>/spec.md` and get it approved.
2. Write the entrypoint `scripts/<name>/main.py`.
3. Optionally scan it with `fused code verify <file>` before committing (nothing runs verify for you).
4. Commit `spec.md` + entrypoint together — the pre-commit hook enforces that spec and entrypoint are always paired in the same commit.

See the **fused-projects** skill for the full spec-first, agent-authored flow (env → project → UDF → run → deploy).

### Deploy a project (`project deploy`)

Batch-deploys all UDFs in a project to a channel. The workspace must be clean (all changes committed) unless `--force` is used.

```sh
fused project deploy taxi-pipeline                     # deploy all UDFs to preview
fused project deploy taxi-pipeline --channel release   # deploy all UDFs to release
fused project deploy taxi-pipeline --force             # bypass dirty-tree check
```

| Option | Default | Notes |
|---|---|---|
| `NAME` | required | Project name |
| `--channel` | `preview` | `preview` or `release` |
| `--force` | false | Deploy even with uncommitted changes |

> `--channel release` bypasses the preview gate and breaks the rollback
> invariant (rollback targets must be prior release events). Use it only for
> bootstrapping the very first release URL — never for a routine production
> release, which goes `deploy` (preview) → `promote`. See the `fused-projects`
> guardrails.

Requires AWS env + `cache_bucket` + provisioned serving plane (`fused infra serve`). Echoes the resolved env name; prints one URL per UDF. Exits 1 if any UDF fails to deploy.

### Promote a project (`project promote`)

Batch-promotes all UDFs in a project from preview to release.

```sh
fused project promote taxi-pipeline
```

### Show project deploy status (`project status`)

Shows the live cloud deploy snapshot for a project. Marks UDFs that are in the cloud snapshot but absent on disk as **orphaned** (prompt to restore or retire).

```sh
fused project status taxi-pipeline
```

Output columns: `UDF`, `CHANNEL`, `COMMIT`, `ORPHANED`, `URL`.

### Deploy a single UDF (`udf deploy`)

```sh
fused udf deploy analysis --project taxi-pipeline
fused udf deploy analysis --project taxi-pipeline --channel release
fused udf deploy analysis --project taxi-pipeline --force
```

| Option | Default | Notes |
|---|---|---|
| `NAME` | required | UDF name |
| `--project WF` | required | Project that owns the UDF |
| `--channel` | `preview` | `preview` or `release` |
| `--force` | false | Deploy even with uncommitted changes |

Requires a clean git tree (or `--force`), AWS env + `cache_bucket`, and a provisioned serving plane. Echoes the resolved env on stderr and prints the channel URL on stdout.

### Promote a single UDF (`udf promote`)

Repoints the release channel to whatever commit preview is currently running.

```sh
fused udf promote analysis --project taxi-pipeline
```

| Option | Default | Notes |
|---|---|---|
| `NAME` | required | UDF name |
| `--project WF` | required | Project that owns the UDF |

### Roll back a single UDF (`udf rollback`)

Rolls back the release channel to a prior commit. Defaults to the previous release commit when `--to` is omitted.

```sh
fused udf rollback analysis --project taxi-pipeline
fused udf rollback analysis --project taxi-pipeline --to abc123def
```

| Option | Default | Notes |
|---|---|---|
| `NAME` | required | UDF name |
| `--project WF` | required | Project that owns the UDF |
| `--to COMMIT` | previous release | Target commit SHA |

### Retire a UDF (`udf retire`)

Revokes the UDF's preview + release mounts, appends a retire event, and drops the UDF from the deploy snapshot. **This cannot be undone via this command.** Prompts for confirmation unless `--yes` is passed.

Retire enforces the same workspace-id conflict gate as deploy/promote/rollback: if the live snapshot was written by a different workspace it refuses unless `--force` is passed (an intentional takeover).

```sh
fused udf retire analysis --project taxi-pipeline
fused udf retire analysis --project taxi-pipeline --yes
fused udf retire analysis --project taxi-pipeline --yes --force   # take over a foreign-owned UDF
```

| Option | Default | Notes |
|---|---|---|
| `NAME` | required | UDF name |
| `--project WF` | required | Project that owns the UDF |
| `--yes` | false | Skip the confirmation prompt |
| `--force` | false | Take over a UDF deployed from a different workspace |

### Pre-commit hook (v6)

The workspace `.git/hooks/pre-commit` is installed/upgraded by `project new` (and by any `bootstrap_workspace` call). Current version: `v6`.

The hook blocks manual commits that touch a UDF's `spec.md` without its `main.py`, or vice versa — including one-sided deletions. The pairing is enforced at depth 4: `<project>/scripts/<udf>/<file>`. Tests, resource files, `main.json` and other files commit freely. fused's own auto-commits are always paired and pass through without `--no-verify`.

Use `git commit --no-verify` to bypass the hook when needed (e.g. fixing a typo in spec.md alone), but note this bypasses the spec↔entrypoint pairing check.

The hook body embeds `# openfused-managed pre-commit hook v6`. On re-install, older managed versions are upgraded; unmanaged hooks (no marker) are warned about and never overwritten.

---

## File storage (`files`)

### List

```sh
fused files list                        # list all buckets
fused files list --bucket my-bucket     # list all keys in bucket
fused files list --bucket my-bucket --prefix data/2024/
```

### Count

```sh
fused files count --bucket my-bucket
fused files count --bucket my-bucket --prefix logs/ --ext .parquet --ext .csv
```

### Get presigned URL

```sh
fused files get --bucket my-bucket --key data/report.parquet
fused files get --bucket my-bucket --key data/report.parquet --expires-in 7200
```

### Schema inspection

Prints column names, types, row count, and file metadata for Parquet, Arrow IPC, or CSV files.

```sh
fused files schema --bucket my-bucket --key data/report.parquet
```

### Upload

```sh
fused files upload data.parquet --bucket my-bucket --key uploads/data.parquet
cat data.csv | fused files upload - --bucket my-bucket --key uploads/data.csv
```

`SRC` defaults to stdin when omitted; `-` also reads from stdin.

---

## Health check (`doctor`)

`fused doctor` surveys **every** project in every workspace under
`~/.openfused/workspaces/` and reports per-project health findings — turning
latent layout/venv drift (the kind that otherwise surfaces as a confusing
`` `.venv` not found `` error at use time) into one up-front, actionable report.

```sh
fused doctor          # read-only survey (default)
fused doctor --fix    # remediate the fixable findings, then re-diagnose
```

**Read-only by default** — diagnosis runs the existing resolvers as pure probes
(never `uv sync`, never rewrites a manifest). It prints one block per
`<workspace>/<project>`; a project with no issues prints `OK`. With no projects
at all it prints `No projects found.`

Findings carry a severity — `BLOCK` (broken / won't run) or `WARN` (degraded):

| `rule_id` | Severity | Meaning | Fixable by `--fix`? |
|---|---|---|---|
| `invalid-name` | BLOCK | Project dir name is not a valid slug | no (rename manually) |
| `legacy-layout` | BLOCK | Legacy v1 UDF folder (`main.py`) at project root, no `scripts/` dir | yes (migrate) |
| `venv-missing` | BLOCK | `scripts/.venv` absent/incomplete | yes (`uv sync`) |
| `venv-stale` | WARN | venv older than `pyproject.toml`/`uv.lock` | yes (rebuild) |
| `stray-root-venv` | WARN | Stale root `.venv` beside a valid `scripts/.venv` | yes (remove) |
| `manifest-legacy` | WARN | `openfused.toml` uses `[workflow]` not `[project]` | yes (migrate) |
| `manifest-unreadable` | BLOCK | `openfused.toml` missing/unparseable or fails validation (e.g. a leftover `kind = "json"` UDF entry) | no (repair manually, or `fused project migrate` to re-sync from disk) |
| `env-unresolved` | BLOCK | Project env doesn't resolve | no (create/pin an env) |

**`--fix`** applies the fixable findings — migrate first (so `scripts/` exists),
then build/refresh the venv and remove stray root venvs — then re-diagnoses and
prints the residual. `invalid-name`, `env-unresolved`, and `manifest-unreadable`
always need a human and are never auto-fixed.

**Exit code:** `doctor` exits `1` when any `BLOCK` finding remains (after
remediation, under `--fix`); `WARN`-only or clean exits `0` — so it works as a CI
gate.

---

## Workspace projects (`project`)

A **project** is a directory rooted at an `openfused.toml` manifest — the unit of
scope and memory. Projects are discovered by directory listing
under `~/.openfused/workspaces/default/` (no registry file). Resolution is
git-style: explicit name → `OPENFUSED_PROJECT` → manifest walk-up from cwd →
global scope (pre-project behavior unchanged).

```sh
fused project create taxi --description "NYC taxi analysis"   # scaffold under workspaces/default/taxi
fused project create taxi --env prod-aws                      # scaffold and pin default_env (validates env exists)
fused project list                       # projects in the default workspace
fused project show [NAME]                # the context packet (see "Show a project")
fused project set NAME --description "new words" --env prod   # update the manifest's [project] keys
fused project set NAME --clear-env       # remove default_env from the manifest
```

> **`project use` was removed.** Select a project with one of:
> - `export OPENFUSED_PROJECT=NAME` — persists across commands in the shell
> - `cd` into the project directory — cwd walk-up resolves automatically
> - `--project NAME` per individual CLI call

`set` updates the `[project]` table of a project's `openfused.toml`
(at least one of `--description` / `--env` / `--clear-env` required; `--env`
and `--clear-env` are mutually exclusive). Edits are style-preserving —
comments, formatting, and unknown keys/tables in the manifest survive — and it
prints the updated `{name, description, default_env}` as JSON.

`create` (like `new`) scaffolds the skill-folder layout: `openfused.toml`, a
`SKILL.md` contract, `scripts/pyproject.toml`, and the `scripts/`, `references/`,
`assets/` convention directories. Each UDF lives as a folder `scripts/<name>/`
with `main.py` as the entrypoint and `spec.md` as its contract — UDFs anywhere
else are not listed or served. A project scopes:

- **environment** — the manifest's `default_env` is used when no `--env` /
  `OPENFUSED_ENV` override is given (explicit override always wins);
- **audit** — events are stamped with the project name; filter with
  `audit log --project NAME`.

Start agent work in a project with `fused project show` — one call returns
identity, the SKILL.md contract, reference notes, UDF scripts, and the resolved
environment.

To expose tools to an MCP host, see `fused app serve` below — there is no
per-project MCP server.

---

## Pipeline graph (`pipeline`)

The project's UDFs wired into a persisted, versioned graph — nodes,
edges, and a `canvas.toml` home. Both commands resolve the
project the same way as `project show` (explicit `--project` → `OPENFUSED_PROJECT`
→ `openfused.toml` walk-up) and emit the `Pipeline` JSON
(`{name, path, version, nodes, edges, viewport}`) to stdout. They are the seam an
app UI reads/writes the canvas through; the graph is a **design-time lens** and
never affects execution.

```sh
fused pipeline graph                        # read the derived/persisted graph as JSON
fused pipeline graph --project taxi          # explicit project
fused pipeline graph --canvas pipelines/reporting/canvas.toml  # a named canvas
fused pipeline derive                        # "create canvas": write canvas.toml + emit reloaded graph
fused pipeline derive --project taxi          # explicit project
```

- **`graph`** reads the graph: it unions the **implicit** UDF→UDF edges (from a
  static `fused.load(...)` scan of each `main.py`) with any **explicit**
  `[canvas].edges` authored in `canvas.toml`. A **missing**
  `canvas.toml` still yields the derivable graph (the implicit-scan floor, `version`
  null); a **corrupt** `canvas.toml` surfaces as a CLI error (non-zero exit), never
  a crash.
- **`derive`** is the derive-and-persist write path: it runs
  the implicit scan, lays nodes out left-to-right by stage depth, and writes a
  `canvas.toml` at the project root (or `--canvas PATH`) capturing the derived nodes
  + edges as **explicit lineage** (whole-document atomic write). It then emits the
  **reloaded** graph, so `version` is the `sha256:<hex>` content hash of the file
  just written. The Python core is the only `canvas.toml` writer (the mutation
  boundary).

---

## Audit log (`audit`)

```sh
fused audit log                          # last 50 events
fused audit log --limit 100
fused audit log --status blocked         # blocked events only
fused audit log --event-type cache_clear
fused audit log --project taxi           # events recorded under one project
```

Events are read from the local SQLite audit store (`~/.openfused/audit.db`).
Flags: `--limit`, `--event-type`, `--status allowed|blocked|warned`, `--project`;
there is no date-range filter and no merge of S3-stored events. What is still
recorded: `cache_clear` (from `share cache-clear`) and the share-mount lifecycle
events. `code run` / `code test` / `code verify` write no audit events, so
`--event-type execute_code` or `verify_code` only returns events from older
installs.

---

## Secrets (`secrets`)

```sh
fused secrets put db-password                # create or update (prompts for the value)
fused secrets get db-password                # print value
fused secrets list                           # all secrets
fused secrets list --prefix db-             # filter by prefix
fused secrets delete db-password             # delete (prompts; --yes to skip)
```

`secrets delete` errors on a missing secret (`Secret '<name>' not found`). On
AWS the secret is **scheduled** for deletion with the default 30-day recovery
window, not force-deleted; on the local backend the name is removed from the
OS keychain map immediately.

**Keep the value off the command line.** `put` takes the value from a no-echo
prompt when you omit it, so the secret never lands in argv — where any other
user on the host can read it (`ps`, `/proc/<pid>/cmdline`) — or in your shell
history. For scripts and CI, pipe it or point at a file:

```sh
printf %s "$DB_PASSWORD" | fused secrets put db-password   # piped stdin
fused secrets put db-password --value-file ./db-password   # from a file ('-' = stdin)
fused secrets put db-password "s3cr3t"                     # inline: works, but exposed
```

One trailing newline is stripped from piped/file input, and an empty read is an
error rather than an empty secret.

**Naming requirement for Lambda access**: the Lambda execution role can only read secrets whose name starts with the environment's function prefix (e.g. `openfused-`). Always prefix secret names with the function prefix when they need to be read from `fused code run`:

```sh
fused secrets put openfused-db-password   # readable from Lambda
fused secrets put db-password             # NOT readable from Lambda
```

Never pass secret values through `code run` inline code strings — retrieve them inside the execution using `openfused.get_secret("openfused-...")` (works on AWS and the local backend).

---

## Code execution (`code run`)

Runs Python code on the resolved environment's backend (Lambda for AWS, a host-venv subprocess for local, Fused's hosted runtime for `fused`). Assign `result` to return a value.

```sh
# Inline code — requires -c/--code
fused code run -c "result = 1 + 1"

# From a file (auto-detected; --file flag is optional)
fused code run myanalysis.py

# From stdin
cat myanalysis.py | fused code run

# Pass local files into the execution context
fused code run myanalysis.py --input-file data.parquet --input-file config.json

# Call a function in the file instead of reading `result`
fused code run myanalysis.py --entrypoint main
```

pip requirements are configured per-environment via `env update -p`, not per-call. Set them once:

```sh
fused env update prod -p pandas -p duckdb
```

Output format (in this order):
- the code's `stdout` is printed as-is
- its `stderr` goes to stderr
- `warning: …` lines, if any
- `result: <value>` when `result` is set, or `result (<media type>, status N):` followed by the body for a non-JSON result
- on failure the error and traceback go to stderr and the command exits non-zero

**Keep the package set stable across calls.** On AWS, packages are baked into the container image — changing them means rerunning `fused infra build-image` (build + ECR push). On local, venvs are cached by a hash of the package set — changing it rebuilds the venv (seconds with uv).

**Caching:** `code run` caches results for **1 hour**, keyed on the code, inputs and environment. There is no flag to disable, refresh or clear this cache. To force a fresh run, change the code or inputs (for example a comment), or wait for the hour to pass. (`code test` does not cache.)

`--monitor-interval` (CloudWatch poll seconds during a run, AWS only) defaults to **10**; the snapshot is printed to stderr while the run is in flight. There is no flag to turn monitoring off.

**Local backend — project venv (`--project` or `--project-dir`).** On a local environment, pass one of:

- `--project <name>` — workspace-registered project; venv must already exist (`uv sync`).
- `--project-dir <path>` — ad-hoc path to any directory containing `openfused.toml`; venv is materialised in place on first run via `uv sync` in `<dir>/scripts/`. Use this for skill-folder bundles (e.g. `~/.claude/skills/<project>`) without registering them in the workspace.

The two flags are **mutually exclusive**. Both are **local-only** — rejected with a clear error on AWS and Fused backends. Without either flag, local execution uses a bare stdlib-only venv (third-party imports fail).

```sh
# Workspace-registered project (venv must already exist)
fused code run myanalysis.py --project taxi-pipeline

# Ad-hoc path (venv materialised on first run via uv sync)
fused code run myanalysis.py --project-dir ~/.claude/skills/taxi-pipeline
```

---

## Security scan without execution (`code verify`)

Scans code and input files for security issues without running it. Packages configured in the resolved environment are scanned for CVEs. Exits 1 if any BLOCK-severity finding is produced.

```sh
# Scan a file
fused code verify myanalysis.py

# Inline scan
fused code verify -c "import subprocess; result = 1"

# Scan code + input files (path traversal in the filename, zip bombs)
fused code verify myanalysis.py --input-file data.zip

# Spec check — Claude reviews whether code matches description (requires an Anthropic
# API key: ANTHROPIC_API_KEY env var, or `fused secrets put anthropic-api-key`, which
# prompts for the key)
fused code verify myanalysis.py --spec "compute the mean of column A"

# Scan using a workspace project's deps
fused code verify myanalysis.py --project taxi-pipeline

# Scan using an ad-hoc project dir's deps (local-only; no backend execute)
fused code verify myanalysis.py --project-dir ~/.claude/skills/taxi-pipeline
```

| Option | Default | Notes |
|---|---|---|
| `-c / --code CODE` | — | Inline code string to scan |
| `--file` | off | Force-treat SRC as a file path (auto-detected when SRC exists on disk) |
| `--input-file PATH` | — | Input file to check for filename path traversal and zip bombs (repeatable). No PII scan runs, despite what `--help` says |
| `--spec TEXT` | — | Natural language description; triggers LLM spec-vs-code check |
| `--project NAME` | — | Scan this project's `pyproject.toml` deps for CVEs (local). Without it, the dep scan uses the AWS env image packages, or nothing on local. Mutually exclusive with `--project-dir`. |
| `--project-dir PATH` | — | Scan using `<dir>/scripts/pyproject.toml` deps (local-only). Mutually exclusive with `--project`. |

The flat `<stem>.spec.md` sidecar auto-discovery and `--no-spec` flag are **removed**. Each UDF now carries one `spec.md` in its own folder. Pass `--spec` explicitly when verifying outside a UDF context.

See the **fused-projects** skill for the spec-first, agent-authored UDF flow.

---

## Test code in Lambda (`code test`)

Runs pytest tests against user code inside the same Lambda environment it will execute in. Returns per-test outcomes, line coverage, and branch coverage. Packages configured in the resolved environment are pre-installed. Exits 1 if any tests fail.

```sh
# Basic usage
fused code test mymodule.py --test-file test_mymodule.py

# With input files available on disk during test run
fused code test mymodule.py --test-file test_mymodule.py --input-file data.csv
```

The test file must import from `user_code`:
```python
from user_code import my_function

def test_basic():
    assert my_function(1) == 2
```

pytest and coverage are auto-installed to `/tmp` on first use when they are not baked into the container image (~30s; warm containers reuse `/tmp/_test_deps`).

**Local backend — `--project` or `--project-dir` is required.** On a local environment, `code test` requires one of these flags. pytest and coverage must be declared as dev dependencies in the project's pyproject.toml; they are not auto-installed in the project venv. Add them in one step with `fused project add-dep <project> pytest coverage --dev` (runs `uv add --dev` + `uv sync`, so the venv isn't left stale). A stale project venv is auto-reconciled on `code run`/`code test` before executing (set `OPENFUSED_NO_VENV_SYNC=1` to opt out).

```sh
# Workspace-registered project
fused code test mymodule.py --test-file test_mymodule.py --project taxi-pipeline

# Ad-hoc path (venv materialised in place on first run)
fused code test mymodule.py --test-file test_mymodule.py \
    --project-dir ~/.claude/skills/taxi-pipeline
```

| Option | Default | Notes |
|---|---|---|
| `-c / --code CODE` | — | Inline code string to test |
| `--file` | off | Force-treat SRC as a file path (auto-detected when SRC exists on disk) |
| `--test-file PATH` | required | Pytest file to run (must import from `user_code`) |
| `--input-file PATH` | — | File extracted to Lambda working directory (repeatable) |
| `--project NAME` | — | Project venv to use (required on local backend; rejected on AWS/Fused). Mutually exclusive with `--project-dir`. |
| `--project-dir PATH` | — | Ad-hoc project dir venv (local-only; materialised on first run). Mutually exclusive with `--project`. |

---

## HTTP serving (`code serve`)

Serves Python code as a live HTTP endpoint (GET and POST) backed by the active compute backend (Lambda or a local host venv). Same source interface as `code run`, plus `--port` and `--host`.

```sh
# From a file → GET+POST /<stem>
fused code serve myudf.py --port 8000

# Inline code — requires -c/--code → GET+POST /run
fused code serve -c "result = 1 + 1"

# From stdin with custom route name → GET+POST /tiles
cat myudf.py | fused code serve --name tiles

# Override route name for a file → GET+POST /api
fused code serve myudf.py --name api --port 8000

# With static files available in every request's execution context
fused code serve myudf.py --input-file model.pkl --input-file config.json

# Bind publicly
fused code serve myudf.py --host 0.0.0.0 --port 8080

# Serve a project directory (multi-entrypoint).
# Folder-per-UDF layout (scripts/ present): each scripts/<name>/main.py → route /<name>.
# Flat layout (no scripts/): each top-level .py file → route /<stem>.
#   Excludes test_*.py / *_test.py / conftest.py / _*.py.
# In both modes, project-root _*.py files are shipped as shared resources.
# (A legacy root-level UDF-folder project must be migrated to scripts/ first —
#  `fused project migrate` — it is not served as-is.)
fused code serve ./my_project   # → GET+POST /daily, /stars, …
```

`--name` is rejected with a directory (each file is its own route); the reserved
route `health` is refused. A single file, `-c`, or stdin is one route.

`code serve` is the **local dev server only** — there is no `--deploy`: deployed
serving is share-only (`infra serve` provisions the plane, `share create` mints
each URL; see those sections).

**GET** — query params become `_params.json`:
```sh
curl "http://localhost:8000/myudf?lat=37.7&lon=-122.4"
```

**POST** — JSON body becomes `_params.json`:
```sh
curl -X POST http://localhost:8000/myudf -H "Content-Type: application/json" \
     -d '{"lat": 37.7, "lon": -122.4}'
```

Access params inside the execution context:
```python
import json
params = json.load(open("_params.json"))
lat = float(params.get("lat", 37.7))
result = {"lat": lat}
```

`result` is serialized as the JSON response body. Unhandled exceptions return `{"error": "<traceback>"}` with status 500. `GET /health` is always registered.

| Option | Default | Notes |
|---|---|---|
| `-c / --code CODE` | — | Inline code string to serve |
| `--file` | off | Force-treat SRC as a file path (auto-detected when SRC exists on disk) |
| `--name` | file stem or `run` | Override the route name |
| `--input-file PATH` | — | File included in every request's execution context (repeatable) |
| `--port` | `8000` | Port to listen on |
| `--host` | `127.0.0.1` | Host to bind (use `0.0.0.0` for public) |
| `--cache-max-age TTL` | `0s` | Cache route results for `TTL` (`s`/`m`/`h`/`d`); `0s` disables. On a hit the compute backend is not invoked; the body returns inline with `X-Openfused-Cache: hit; age=<s>` / `miss` |
| `--cache-allow-bypass` | off | Honour `Cache-Control: no-cache` to force a fresh execution and rewrite the entry |

### Deployed serving moved (`infra serve` + `share`)

`code serve --deploy`, `code serve --teardown`, and `code serve-list` **no longer
exist** (on any backend — the local background-process deploy is gone too).
Deployed serving is share-only:

- **`fused infra serve`** provisions the environment's serving plane (one
  HTTP API + one dispatcher Lambda) — see *Infrastructure* below;
- **`fused share create`** publishes an app and mints its URL with the access
  control you choose — see the `share` section below;
- **`fused share revoke`** / **`infra serve --rate-limit 0`** /
  **`infra serve --teardown`** take things down at the URL / plane level.

---

## Served URLs / share links (`share`)

The share-only URL model: `share create` is the **only**
URL-minting operation — it publishes an app (a `.py` file or a project directory)
as a content-addressed artifact and writes the mount record binding a token to it
with the access control you choose. Publishing never builds infrastructure.

It dispatches on the resolved environment's backend:

- **AWS** — publishes to the env's cache bucket and serves through the plane
  `infra serve` provisions. Requires a `cache_bucket`. All verbs work.
- **Fused** (managed) — uploads the source and mints the mount through the
  control-plane mounts API (needs `fused cloud login`). `create`, `list`,
  `repoint`, `recreate`, `revoke`, `update`, `errors` and `cache-clear` work;
  `show` is AWS-only. There is no `infra serve` — Fused operates the plane.

Every lifecycle op is audited (`share_create`/`share_revoke`/`share_recreate`/
`share_repoint` in `audit log`).
```sh
# Authed mount (default: Login with Fused) — token auto-derived from the stem
# (my_file.py → /my-file); audience from --jwt-audience or the env's
# serve_auth.default_audience (required — errors without one)
fused share create my_file.py

# Public share link — mints a crypto-random opaque token (the token IS the
# credential; a guessable public URL is never produced by accident)
fused share create --public my_file.py

# Named public mount — deliberately guessable; requires the explicit --token
# (prints a warning)
fused share create --public --token acme-dash my_file.py

# Custom issuer (must be on the env's serve_auth.issuer_allowlist) / ACL
fused share create --jwt-issuer https://idp.acme.io/ --jwt-audience proj my_file.py
fused share create --acl-subject alice@acme.io --acl-group analysts my_file.py

# Allow a browser origin to call the mount (repeatable for multiple origins)
fused share create --public --cors-origin https://app.acme.io my_file.py

# Whole project directory (entrypoints discovered like `code serve <dir>`),
# or a single entrypoint of it; --not-after sets a hard expiry
fused share create ./project
fused share create ./project --entrypoint daily --not-after 2026-12-31T00:00:00Z

# Inspect (list shows YOUR mounts; --all for everyone's)
fused share list
fused share list --all
fused share show my-file

# Revoke — the record becomes a tombstone: the token stays reserved (no other
# principal can ever claim it) and the mount goes dark within the plane's
# mount-cache TTL; --confirm forces the strong flush (dispatcher recycle —
# no new invocation sees the old record)
fused share revoke my-file
fused share revoke my-file --confirm

# Recreate: a FRESH opaque token for the same target (default — right for a
# leaked link), or revive the SAME token in place (owner-only)
fused share recreate my-file
fused share recreate my-file --same-token

# Repoint: update an ACTIVE mount's target in place — URL/token UNCHANGED.
# Publishes new-code.py, bumps the mount's version, and emits share_repoint
# in the audit log. Auth flags update the gate; omit to keep the existing gate.
fused share repoint my-file new-code.py
fused share repoint my-file new-code.py --entrypoint daily
fused share repoint my-file new-code.py --public
fused share repoint my-file new-code.py --jwt-audience new-proj
# --confirm forces the strong flush so the change is visible immediately
# (without it the update is visible within the mount-cache TTL, typically ≤5 min)
fused share repoint my-file new-code.py --confirm

# Result caching for the mount, and letting viewers download the page source
fused share create my_page_dir --cache-max-age 5m
fused share create my_page_dir --allow-clone

# Change posture in place (no SRC, no republish, same URL)
fused share update my-file --no-allow-clone

# Bust every cached result under a mount (the only cache-clear command)
fused share cache-clear my-file

# Owner-side detail behind an opaque deployed 500 {"error": "internal error", "id": …}
fused share errors my-file                 # newest-first records for one mount
fused share errors my-file <err-id>        # one full record
fused share errors --env --since 2h        # sweep the whole environment
```

Key rules: token auto-generation is gate-aware (authed → stem-derived name,
public → crypto-random opaque; `--random-token` forces opaque on an authed
mount). Creation is **owner-bound** — only the principal that published an app
(the normalized STS caller ARN, or `OPENFUSED_CALLER_NAME` without AWS
credentials) may mint mounts of it, and revoke/recreate are owner-guarded the
same way. Re-running `share create` with identical content is an idempotent
republish. `recreate` requires the mount to be revoked first. `repoint`
requires the mount to be **active** — revive a tombstone first with
`recreate --same-token` before repointing it.

`--cache-max-age TTL` (e.g. `5m`, `1h`, `0s`): on AWS it applies to fused-render
page bundles only and overrides the bundle manifest's own `cache_max_age`; on
Fused it applies to any mount. `--allow-clone` (fused-render pages only, off by
default) lets anyone who can reach the URL **download the page's source
bundle** — with `--public` that publishes the page's Python source to anyone
holding the URL. Turn it off again with `share update TOKEN --no-allow-clone`.

---

## Infrastructure (`infra`)

The `infra` commands work for the AWS and local backends; each command
dispatches by the resolved environment's backend (they are not supported on the
Fused backend).

### Plan / apply / teardown

```sh
fused infra plan        # dry run — exits 1 if changes needed
fused infra apply       # reconcile IAM role, Lambda functions to desired state
fused infra teardown    # delete all fused Lambdas + IAM role (prompts for confirmation)
fused infra teardown --yes   # skip prompt
```

`infra plan` is useful in CI: a non-zero exit code signals drift.

`infra teardown` does **not** delete S3 buckets or Secrets Manager secrets — it removes Lambda functions, the managed IAM role, and optionally the ECR repository.

### Local backend

For a `backend: "local"` environment, "infra" is the data/secrets/venvs
directories and the cached venv holding the env's `packages` (no cloud
resources):

```sh
fused infra plan          # reports missing dirs (exits 1 on drift)
fused infra apply         # create dirs (idempotent; bare venv is created lazily on first execute)
fused infra teardown      # remove the venvs dir + data dir (prompts); serve endpoints survive
fused infra lambda-reset  # clear the in-process venv ready-cache (nothing deleted from disk)
```

- `infra build-image` **errors** for local envs — there is no image; packages go
  into a cached venv, provisioned by `infra apply` (or lazily on first execute).

### The serving plane (`infra serve`)

Deployed serving's compute, managed like every other resource family. Provisions
one HTTP API (v2) + one dispatcher Lambda per environment; **mints no URLs** —
URLs come only from `share create`. Requires an AWS env with `cache_bucket`, and
Docker to build the dispatcher image (the fused package on the Lambda Python
base; `--image-uri` registers a pre-built image instead). Idempotent.

```sh
# Provision (or reconcile) the plane
fused infra serve

# Plane-wide rate limit; 0 = kill-switch (every mount answers 429, URLs stay
# stable; re-apply with N>0 to re-enable). Omitted = leave unchanged.
fused infra serve --rate-limit 50
fused infra serve --rate-limit 0

# Custom domain (every mount is hosted under it by path)
fused infra serve --domain api.example.com --cert-arn arn:aws:acm:...

# Remove the plane: every mount goes dark; mount records + published apps
# persist until `infra teardown`. Prompts unless --yes; takes no other options.
fused infra serve --teardown --yes
```

`infra teardown` also sweeps the plane (the `{prefix}serve` API, the dispatcher
Lambda, the serve ECR repo) along with everything else.

### Container image

AWS Lambda execution is **container-only**: the ECR image built here is the function's code (one `{prefix}container` function per env). There is no fallback — until an image is configured, `fused code run` fails with an error telling you to run `infra build-image`. Bake the packages you need into the image; per-call pip installs do not happen.

**Step 1 — configure the image in the environment** (one-time or when packages change):

```sh
fused env update prod \
  -p pandas -p pyarrow -p duckdb \
  --python-version 3.12
```

**Step 2 — build and push** (run again whenever you want to rebuild):

```sh
fused infra build-image
```

| Option | Default | Notes |
|---|---|---|
| `--image-uri` | — | Skip build; register a pre-built image |
| `--push / --no-push` | push | Push to ECR after build |
| `--builder` | env's `builder` (`codebuild`) | `codebuild` (default; remote AWS CodeBuild, no local Docker) or `local` (docker build on host) |

Build parameters (`-p/--package`, `--system-dep`, `--python-version`, `--image-platform`, `--image-repo`, `--image-tag`, `--builder`, `--dockerfile`, `--context-dir`) live in the environment config and are set via `env create` or `env update`. `infra build-image` reads them automatically.

After a successful build and push, the image is resolved to its digest URI (`…@sha256:…`) and stored in the resolved environment's `docker_image` field. Using the digest rather than the mutable tag (`:latest`) means `infra plan` can detect when a new image has been built and flag the Lambda function for update.

**CodeBuild is the default (no local Docker).** `infra build-image` builds remotely in AWS CodeBuild by default — no Docker daemon needed on your machine — using the env's cache bucket (the build source is uploaded there). Pass `--builder local` to build with the host Docker daemon instead. CodeBuild also accepts a user-supplied build context:

```sh
fused infra build-image                               # builds in CodeBuild (default); streams logs
fused env update prod --context-dir ./img --dockerfile Prod.Dockerfile  # your own Dockerfile + context
fused infra build-image --builder local -p duckdb    # opt into a host docker build
```

CodeBuild builds in your own AWS account and pushes via a service role whose ECR push is scoped to just the env's repo. `infra apply` also uses CodeBuild when the env's `builder` is `codebuild` (the default). `infra teardown` removes the CodeBuild project and its role. With no cache bucket configured (a deliberate `--no-cache-bucket`), the CodeBuild build fails fast with guidance to set one or pass `--builder local`. Limitation: concurrent builds sharing the same image tag aren't supported (the digest is resolved by the mutable tag).

---

## Serving an app's tools to an MCP host (`app serve`)

```sh
fused app serve /abs/path/to/app
```

`app serve APP_DIR` reads the `[[tool]]` tables from `APP_DIR/mcp.toml` and
publishes exactly those as tools on a **stdio MCP server**. Each call runs through
the **local** compute backend — an app's entrypoints read the author's own token
files and localhost services — so `--env` / the resolved environment are never
consulted. `mcp.toml` is authored by fused-render's MCP panel; a missing or
invalid one fails at startup, before the MCP handshake, so the host reports a
startup error rather than connecting to an empty tool list.

Point an MCP host at it with:

```json
{"command": "fused", "args": ["app", "serve", "/abs/path/to/app"]}
```

This is the only MCP surface `fused` ships. There is no general-purpose fused MCP
server (bare `fused` prints help), no `project serve --mcp` / `code serve --mcp`,
and no `widget`, `dev serve` or JSON-UI commands.

---

## Host extras (`fused[...]`)

Optional features need extras installed **on the host** where you run `fused`
(they are not packages inside the execution sandbox — use `env update -p` or
`project add-dep` for those):

| Extra | Installs | Needed for |
|---|---|---|
| `data` | pyarrow, pandas, numpy | `files schema`, and `fused.run()` returning a DataFrame (included in `aws`) |
| `aws` | boto3 + `data` | any AWS environment (Lambda, S3, Secrets Manager, `infra`, `share` on AWS) |
| `verify` | anthropic, ty | `code verify --spec` (the LLM spec check) and the type checker |
| `local` | keyrings.alt | local-backend secrets where there is no OS keychain (Linux/WSL; stores unencrypted) |
| `geo` | geo stacks + `data` | the legacy workbench geo SDK (`batch`, `raster`, `vector` are aliases) |
| `workbench` | selenium, fastmcp | the `fused workbench` CLI's JSON-UI and MCP commands |
| `all` | every extra except `local` | everything, without the plaintext secrets fallback |

Combine them as needed, e.g. `uv tool install 'fused[aws,verify]'`. `fused app serve`
needs no extra.

---

## Common patterns

### First-time AWS setup

```sh
fused env create prod --backend aws --prefix myapp- -p pandas
# Provisions IAM role + cache bucket
fused infra build-image   # build + push the Lambda container image (required before execution)
fused infra apply         # creates the {prefix}container Lambda from the image
fused infra plan          # verify no further drift
```

### Targeting a specific environment for a single command

```sh
fused --env staging secrets list   # uses staging for this command only
```

### CI drift check

```sh
fused infra plan || echo "Infrastructure out of sync — run apply"
```

### Inspecting a dataset before running expensive code

```sh
fused files schema --bucket my-bucket --key data/large.parquet
fused files count --bucket my-bucket --prefix data/ --ext .parquet
```
