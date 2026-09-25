---
name: fused-projects
description: The canonical end-to-end guide for an agent driving Fused — pick an environment, create a project, decompose a task into UDFs, author specs and code, validate + commit, run locally, and deploy through preview to release. Code is authored by the driving agent (no codegen command, no API key); fused supplies validation, the spec↔code pairing hook, and run/deploy, all through the `fused` CLI. Use to take a user request from prompt to a running result.
---

# Driving Fused end-to-end (spec-first, agent-authored)

> **Part of the Fused skill set — don't work from it alone.** Load
> **`fused-execute`** for how code runs and **`fused-verify`** for scanning and
> tests. See **`fused-guide`** for the full set.

Fused organises work as **workspace ⊃ project ⊃ UDF**. You — the driving
agent — author the specs and the code; Fused supplies the scaffold, the
deterministic validators, a spec↔code consistency hook, and the run/deploy
machinery. There is **no code-generation command and no API key** in the loop:
authoring code *is your job*.

Every step goes through the `fused` CLI (there are no MCP tools). User projects live
in the `default` workspace at `~/.openfused/workspaces/default/<project>/`.

The full loop:

```
user request
  → pick an environment (local-first for dev)
  → decompose into projects + UDFs
    → write spec.md per UDF  → user approves SPECS (never code)
      → author main.py yourself
        → fused code verify → git commit (the pairing hook keeps spec+code in sync)
          → fused code run / code test locally
            → deploy to preview → promote to release (AWS)
```

The **spec is the only artifact the user reviews**.

| Step | Command |
|---|---|
| Create/select an env | `fused env create` / `fused env list` / `fused env show` |
| Create a project | `fused project new` (or `project create`) |
| Write spec.md / author code | **you write the files** (no command) |
| Validate code | `fused code verify` |
| Commit (spec+code together) | `git commit` — the pre-commit hook enforces pairing |
| Inspect a project | `fused project show` (context packet) / `fused project list` |
| Run / test code | `fused code run` / `fused code test` |
| Deploy / promote / roll back / retire | `fused project deploy|promote`, `fused udf deploy|promote|rollback|retire` |
| Deploy status | `fused project status` |

---

## Step 0 — Pick an environment (local-first)

You do not need a cloud account to build and run. For development, use the
**local** backend (code runs in a project venv on the host):

```sh
fused env create dev --backend local
```

AWS is the production target (deploys UDFs to stable URLs); set it up later via
the **fused-setup** skill. **Resolution:** if more than one env exists,
nothing is auto-selected — pin the project (`fused project set <project>
--env dev`) or pass `--env`/`OPENFUSED_ENV`. Verify with `fused project show`
(`environment.resolved_env`).

> An unpinned project with multiple envs makes `code run` and other commands fail
> to resolve an environment. Pin early.

---

## Step 1 — Decompose into UDFs

Decide the UDFs. Each UDF is a folder `scripts/<name>/` with a `main.py`
entrypoint and a `spec.md` contract. It does one computation/API call and returns a
value (often a DataFrame).

Each UDF is one independent capability — lean small. Slugs:
`^[a-z][a-z0-9]*([-_][a-z0-9]+)*$`, ≤64 chars — `-` and `_` are both accepted as
segment separators, so snake_case names like `list_comments` are valid
(e.g. `sessions`, `dashboard`, `list_comments`). Names starting with `_` are not
valid slugs.

---

## Step 2 — Create the project

```sh
fused project new taxi-pipeline
```

Scaffolds `openfused.toml`, `SKILL.md`, and the `scripts/ references/ assets/`
convention dirs (with `scripts/pyproject.toml` and `scripts/tests/`); on first use it
initialises the `default` workspace as a git repo with the openfused-managed
pre-commit hook.

**It also seeds `scripts/.venv`** (runs `uv sync` against the scaffolded
`pyproject.toml`, which has an **empty dependency list**) so the first local
`code run` starts fast. Seeding is best-effort — if `uv` is missing or `uv sync`
fails, the project is still created and `project new` prints a warning on stderr.

**Add the packages your UDFs import before the run step.** Use `project add-dep`,
which runs `uv add` + `uv sync` in one step so the venv is never left stale:

```sh
fused project add-dep taxi-pipeline duckdb pandas          # UDF runtime deps
fused project add-dep taxi-pipeline pytest coverage --dev  # only if you'll run `code test`
```

(Equivalent manual form: `cd …/taxi-pipeline/scripts && uv add … && uv sync`. A
stale venv left by a bare `uv add` is auto-reconciled on the next local
`code run`/`code test` unless `OPENFUSED_NO_VENV_SYNC` is set.)

> `project new <name>` is the simple scaffold. `project create <name>` is the same
> scaffold plus `--description` / `--env` (pin the env in one shot). Prefer
> `project new` for the plain case.

**Make the project's `SKILL.md` a real contract.** It is the project's agent-facing
description (surfaced as `contract` by `project show`): what the project does, its
UDFs and their parameters, and how to run them. Replace the scaffold's placeholder
text.

---

## Step 3 — Write the specs

For each UDF, **write `scripts/<name>/spec.md` yourself** (create the folder if
needed). Fused does not draft specs — you do:

```markdown
# taxi-analysis

Joins NYC taxi trips to zone boundaries and returns mean fare per zone.

## Inputs
- `bucket` (str), `prefix` (str)

## Output
DataFrame: `zone_id`, `zone_name`, `mean_fare`, `trip_count`

## Notes
- Use DuckDB for the join; filter zones with < 10 trips.
```

Specs are free-form markdown; the more precise, the better the code.

---

## Step 4 — Get approval on the SPECS

**Stop and get the user to review the specs before writing code.** Present each
spec (the full `spec.md`, or a diff against the previously approved version on a
revision round) and ask for approval or requested changes. On approval → author the
code (Step 5). On requested changes → edit the specs and ask again; loop until
approved. Summarise if multiple UDFs are pending.

---

## Step 5 — Author the code yourself

Write `main.py` into each UDF folder to satisfy its spec. **You are the codegen** —
there is no generate command. Iterate by editing the spec *and* the code together
(keep them consistent — Step 6's hook enforces it).

```python
import fused

@fused.udf
def main(threshold: int = 0):
    ...
    return df          # a DataFrame, or a scalar
```

- Prefer a `@fused.udf` entrypoint (takes params; portable; works as a fan-out
  worker and a served route). A bare top-level `result = <value>` is fine for a
  quick no-param script. **Never both** in one file.
- To read a file shipped in the project's `assets/`, use `openfused.asset_path(...)`
  rather than a hard-coded path.
- See **fused-execute** for libraries, secrets and S3 patterns.

---

## Step 6 — Validate, then commit

Validate the code through the deterministic scanners (see **fused-verify**), then
commit the spec+entrypoint **together**:

```sh
cd ~/.openfused/workspaces/default/taxi-pipeline
fused code verify scripts/taxi-analysis/main.py --project taxi-pipeline
git -C ~/.openfused/workspaces/default add taxi-pipeline/scripts/taxi-analysis/
git -C ~/.openfused/workspaces/default commit -m "taxi-analysis: spec + impl"
```

The **pre-commit hook blocks one-sided commits** — a `spec.md` without its
`main.py`, or vice versa — so every committed state is internally consistent.
`git commit --no-verify` is the escape hatch for a genuine one-sided change (e.g.
fixing spec prose with no code change).

UDFs are discovered by **directory listing** (`scripts/<name>/` containing
`main.py`), so a freshly authored UDF is already visible to run and deploy — you do
not need to register it. A folder with only a `main.json` (or any other file) is
**not** a UDF; `main.json` is just a file. `fused project show` reports the UDFs it
finds (`udf_scripts`) but does not rewrite the manifest's `[udfs.*]` table.

> **Manifest repair.** If `openfused.toml` still carries a `kind = "json"` UDF entry
> from an older layout, reading the manifest fails validation (and `fused doctor`
> reports `manifest-unreadable`). `fused project migrate <name>` rebuilds the
> `[udfs.*]` table from disk and fixes it.

> **`archive/` — soft-deleted artifacts, never enumerated.** A project may carry a
> top-level **`archive/`** directory that mirrors the layout
> (`archive/scripts/<udf>/`, `archive/references/<name>.md`, …). It holds artifacts a
> human archived in an app — a reversible soft-delete. Discovery is a shallow,
> by-name scan of the *live* dirs, so archived artifacts are **invisible** to
> `project show`, `pipeline graph`, and deploy; deploying an archived UDF is simply
> "not found". `archive/` is git-tracked, but it is **not yours to author into**:
> never write into it, treat it as a UDF source, or "restore" by hand-moving files.

> **`work-products.json` — app-owned, read-only to you.** A project managed by an app
> may carry a `work-products.json` at the project root (git-tracked) recording each
> artifact's status and provenance. The app is its single writer — never hand-author,
> edit, or commit a change to it. The `fused` CLI has no command that writes it.
> Editing a file leaves its recorded `version` stale; that is expected.

> **Hard-delete a whole project: `fused project delete <name>`.** Distinct from
> `archive/`, this removes the project from the workspace: `git rm -rf -- <name>` + a
> `--no-verify` commit, then cleans gitignored residue (`scripts/.venv`,
> `__pycache__`). It prints JSON `{name, deleted, root}`.

---

## Step 7 — Run locally

**Local backend needs the project venv to have your UDFs' imports** (Step 2). If a
UDF you just wrote imports something new, add it first:

```sh
fused project add-dep taxi-pipeline <new-dep>
```

**Run a UDF:**

```sh
fused code run scripts/taxi-analysis/main.py --project taxi-pipeline
```

**Test it** (`code test` requires `--project` or `--project-dir` on the local
backend, and pytest + coverage as dev deps):

```sh
fused code test scripts/taxi-analysis/main.py --test-file scripts/tests/test_taxi.py \
  --project taxi-pipeline
```

Note that `code run` caches results for 1 h (see **fused-execute**): re-running
unchanged code within the hour returns the previous result.

To try a UDF as a local HTTP endpoint, `fused code serve scripts/ --port 8000`
serves every `scripts/<name>/main.py` at `/<name>` (see **fused-cli**).

---

## Step 8 — Deploy to preview (AWS)

Prerequisites (AWS only): an AWS env with `cache_bucket`, resolved for this project,
and a provisioned serving plane (`fused infra serve`). Verify the resolved env first
(`fused project show` → `environment.resolved_env`).

```sh
fused project deploy taxi-pipeline                  # all UDFs → preview
fused udf deploy taxi-analysis --project taxi-pipeline
```

Each UDF deploys to an HTTP route. The response echoes `env: <name>` and a preview
URL per UDF — **verify the env matches your intent.** Deploy always targets
`preview`; release moves only via promote/rollback.

---

## Step 9 — Promote to release

```sh
fused project promote taxi-pipeline
fused udf promote taxi-analysis --project taxi-pipeline
```

Repoints release to whatever commit preview runs; the release URL is stable from
first promote. Roll back with `fused udf rollback … [--to <commit>]` (only prior
release commits are valid targets). Check the live state with
`fused project status taxi-pipeline`.

---

## Iterating

Behaviour wrong? **Edit `spec.md` and the code together** (both under
`scripts/<name>/`), re-run `fused code verify`, re-run, and commit (the hook keeps the
pair consistent). There is no regenerate command — you re-author the changed UDFs.

---

## Guardrails

### Spec-first, agent-authored
The user reviews specs, not code. Author code only after spec approval. Keep
`spec.md` and `main.py` consistent — the pre-commit hook enforces it on commit.

### The env is resolved per project — verify before deploying
Every deploy/promote/rollback echoes `env: <name>`. If it is wrong, pin
(`fused project set <project> --env <name>`) or override (`--env` /
`OPENFUSED_ENV`). With a single env it auto-selects; with several you must pin.

### Deploy to preview first; promote to release
The two-channel model exists so code passes through preview before release.
`udf deploy --channel release` is only for bootstrapping the very first release
URL.

### Retiring a UDF
`fused udf retire <udf> --project <p> --yes` revokes both channel mounts and drops
the UDF from the cloud snapshot (the on-disk folder stays). It is destructive —
confirm with the user first. A UDF present in the cloud snapshot but absent on disk
shows as **orphaned** in `project status`.

### No list of deployed UDFs across projects
There is no CLI command that lists every deployed UDF in an environment. Use
`fused project status <project>` per project, or `fused share list` for the mounts.

---

## See also

- **fused-execute** — `code run` patterns (libraries, S3, secrets, caching).
- **fused-verify** — `code verify`, `code test`, `audit log`.
- **fused-setup** — install + AWS env provisioning.
- **fused-cli** — full command/flag reference.
