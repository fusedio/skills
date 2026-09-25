---
name: fused-execute
description: Best practices for running code with `fused code run`. Use when writing or reviewing code you will execute through the fused CLI — covers how to structure user code, choose a data library, handle results, write outputs to the file store, pick a project venv, fan out, and what caching `code run` applies. For static scanning, spec checks, and testing see fused-verify. If this is part of building or running a project, load `fused-projects` first for the end-to-end model.
---

# Running code via fused

> **Part of the Fused skill set — don't work from it alone.** Fused is `workspace ⊃
> project ⊃ UDF`. If the task is part of building or running a project (not a
> one-off snippet), load **`fused-projects`** for the end-to-end model. See
> **`fused-guide`** for the full set.

Code runs through the CLI (there is no MCP `execute_code` tool any more):

```sh
fused code run my_udf.py                    # a file
fused code run -c "result = 1 + 1"          # inline
cat my_udf.py | fused code run              # stdin
fused code run my_udf.py --input-file ./points.parquet   # stage a local file (repeatable)
fused code run my_udf.py --entrypoint compute            # call a named function
fused --env prod code run my_udf.py         # pick the environment explicitly
```

Output: the code's stdout, then stderr, any `warning: …` lines, and finally
`result: <value>` — or `result (<media_type>, status N):` followed by the body
when the code returns a `fused.Response`. Runtime errors (tracebacks) appear on
stderr. On AWS, a CloudWatch monitoring snapshot is printed to stderr every
`--monitor-interval` seconds (default 10) while the Lambda runs.

## Core principle: code should do one thing

The code passed to `code run` should be as focused as possible:
- One clear task per execution
- No boilerplate, no CLI argument parsing, no `if __name__ == "__main__"` guards
- Return the result from a `@fused.udf`-decorated function (preferred), or assign it to a top-level `result` variable

## Choosing how to return: `@fused.udf` vs `result`

**Prefer a `@fused.udf` entrypoint over a top-level `result =` assignment.** Both
return the value identically, but a UDF is the more capable, portable form:

- It takes parameters, so the same code runs standalone *and* as a fan-out worker
  (`.map()` / `fused.load()`) or a served route — kwargs arrive via `_openfused_args.json`.
- It matches the real `fused` SDK, so code moves between fused and Fused unchanged.
- It keeps the return value in an explicit `return`, not a magic module global.

```python
import fused

@fused.udf
def main(threshold: int = 0):
    ...
    return {"count": n}        # becomes the return value
```

Use a bare `result = <scalar>` only for a quick one-off where there are no
parameters and you won't reuse the code (e.g. `result = df.shape[0]`).

The two are **mutually exclusive** — a script returns via a `@fused.udf` *or* a
`result` variable, never both; using both (including `result = None` alongside a
UDF) is an error. `--entrypoint NAME` overrides the convention and calls the named
function directly.

## Returning results

**Prefer writing to S3 over returning data inline.**

The return value is serialized as a string and printed after `result:`. That works
fine for scalars (a URL, a count, a status message), but large DataFrames or binary
blobs make the output unusable.

The right pattern:

1. Compute the output inside the code
2. Write it to S3 using `boto3` inside the same code
3. Return the S3 key or a presigned URL — not the data itself
4. If a download URL is needed afterwards: `fused files get --bucket B --key K`

Only return inline when the value is a simple scalar: a number, a short string, a boolean.

## Writing DataFrames to S3

Write DataFrames to the environment's **cache bucket** (or a bucket you own)
rather than returning them inline. Get the bucket name with `fused env show`
(the `cache_bucket` field), then embed it in the code (it is not a secret).

```python
import boto3, io

# ... compute df ...

buf = io.BytesIO()
df.to_parquet(buf, index=False)
buf.seek(0)

s3 = boto3.client("s3")
bucket = "openfused-abc123"   # from `fused env show` → cache_bucket
key = "outputs/my_result.parquet"
s3.put_object(Bucket=bucket, Key=key, Body=buf.read())

result = f"s3://{bucket}/{key}"
```

**Choosing what to return:**

| Use case | Return |
|---|---|
| Follow-up commands | `f"s3://{bucket}/{key}"` (path only) |
| User download / sharing | Presigned URL — either `fused files get --bucket … --key …` afterwards, or generated inside the code with `boto3` |

To generate the URL inside the code (avoids an extra step when the user explicitly
asks for a URL):

```python
import boto3

s3 = boto3.client("s3", region_name="us-west-2")
bucket, key = "openfused-abc123", "outputs/my_result.parquet"
s3.put_object(Bucket=bucket, Key=key, Body=buf.read())

result = s3.generate_presigned_url(
    "get_object",
    Params={"Bucket": bucket, "Key": key},
    ExpiresIn=3600,
)
```

When writing output via DuckDB `COPY … TO 's3://…'` is not possible due to
region/credential mismatch, write to `/tmp/` first then upload with `boto3`:

```python
conn.execute("COPY (SELECT …) TO '/tmp/output.parquet'")
with open("/tmp/output.parquet", "rb") as f:
    s3.put_object(Bucket=bucket, Key=key, Body=f.read())
```

## Choosing a data library

Prefer libraries in this order:

1. **DuckDB** — best default for SQL-style analysis, reading Parquet/CSV directly from S3, and aggregations over large files. Zero-copy, no materialisation until needed.
2. **Polars** — preferred for Python-native DataFrame transformations. Lazy API, fast, low memory footprint.
3. **Pandas** — use only when an existing snippet, library, or output format requires it.

Whatever you pick must be installed where the code runs — see **Requirements**.

## DuckDB S3 setup

**AWS Lambda:** Lambda has no writable home directory by default. Always create one in `/tmp` and pass it via the `config` dict — using `SET home_directory=...` after connection does not work reliably in Lambda.

```python
import duckdb, os

os.makedirs("/tmp/duckdb_home", exist_ok=True)
conn = duckdb.connect(config={"home_directory": "/tmp/duckdb_home"})
conn.execute("SET s3_region='us-east-1'")   # match the bucket's region
conn.execute("INSTALL httpfs; LOAD httpfs")
```

**S3 region**: set `s3_region` to the region of the bucket you are reading from, which may differ from the Lambda's own region. Public buckets (e.g. `fused-asset`) are typically in `us-east-1`; the fused cache bucket (`openfused-cache`) is in `us-west-2`. If you read from one and write to the other, update `s3_region` between the two operations.

```python
# DuckDB reading Parquet directly from S3 (no download needed)
import duckdb
con = duckdb.connect()
result_df = con.execute(
    "SELECT col, COUNT(*) FROM read_parquet('s3://my-bucket/data/*.parquet') GROUP BY col"
).df()
# write result_df to S3 ...
```

```python
# Polars over a file staged with --input-file (lands in /tmp/context/)
import polars as pl
df = pl.read_parquet("/tmp/context/input.parquet")
out = df.filter(pl.col("value") > 0).group_by("category").agg(pl.col("value").sum())
# write out to S3 ...
```

### Passing file paths to DuckDB — Python variables vs SQL

DuckDB's `conn.execute(sql)` runs SQL; it cannot reference Python variables by name. A common mistake when building file lists dynamically:

```python
# WRONG — 'paths' is a Python list; DuckDB SQL treats it as a column name
paths = ["s3://bucket/a.parquet", "s3://bucket/b.parquet"]
conn.execute("SELECT * FROM read_parquet(paths)")   # BinderError

# RIGHT — use parameter binding
conn.execute("SELECT * FROM read_parquet(?)", [paths])
```

## Geospatial data

For any spatial analysis involving latitude/longitude points, use **H3** (Uber's hierarchical hexagonal grid). It is faster to join, aggregate, and visualize than raw coordinates.

```python
import io, boto3, h3
import polars as pl

df = pl.read_parquet("/tmp/context/points.parquet")  # has lat, lng columns

# Index points into H3 hexagons at resolution 8 (~460 m)
df = df.with_columns(
    pl.struct(["lat", "lng"])
    .map_elements(lambda r: h3.latlng_to_cell(r["lat"], r["lng"], 8), return_dtype=pl.Utf8)
    .alias("h3_cell")
)

agg = df.group_by("h3_cell").agg(pl.len().alias("count"))

buf = io.BytesIO()
agg.write_parquet(buf)
buf.seek(0)
boto3.client("s3").put_object(Bucket="openfused-abc123", Key="outputs/h3_agg.parquet", Body=buf.read())
result = "s3://openfused-abc123/outputs/h3_agg.parquet"
```

Choose the H3 resolution based on desired granularity:

| Resolution | Avg cell area | Typical use |
|---|---|---|
| 5 | ~252 km² | Country/region |
| 7 | ~5.2 km² | City district |
| 8 | ~0.7 km² | Neighborhood |
| 10 | ~15 000 m² | Block |
| 12 | ~320 m² | Parcel / fine-grained point |

## Requirements

`code run` has no per-call requirements flag. What the code can import depends on
the backend:

**AWS backend:** packages are baked into the env's container image. Add them with
`fused env update <env> -p duckdb -p polars`, then `fused infra build-image`
(builds + pushes the image and records its digest URI as `docker_image`) and
`fused infra apply` (points the env's `<prefix>container` Lambda at it). Nothing is
pip-installed at invocation time.

**Local backend:** `-p/--package` is AWS-only. Third-party dependencies belong to a
project's `scripts/pyproject.toml`; add them with
`fused project add-dep <project> <pkg>` (runs `uv add` + `uv sync`) and run with
`--project` / `--project-dir`. Without a project, execution runs in a bare
stdlib-only venv, so third-party imports fail.

**Fused backend:** only packages pre-baked into the Fused runtime are available.

The extras installed on the host (`fused[aws]`, `fused[arrow]`, …) do **not**
change what the executed code can import.

## Project venvs on the local backend

When executing against a **local** environment, use one of two selectors to run
inside a project's venv.

### `--project NAME` (workspace mode)

```sh
fused code run myanalysis.py --project taxi-pipeline
```

- Resolves `<workspace>/taxi-pipeline/scripts/.venv/bin/python`.
- The project's `default_env` pin is honoured when picking the environment.

### `--project-dir PATH` (ad-hoc / path mode)

```sh
# Run a skill-folder bundle anywhere on disk — no workspace registration needed
fused code run myanalysis.py --project-dir ~/.claude/skills/taxi-pipeline

# Code test with a path-addressed project
fused code test mymodule.py --test-file test_mymodule.py \
    --project-dir ~/.claude/skills/taxi-pipeline

# Dep-scan verify using the project dir's pyproject.toml (no execution)
fused code verify myanalysis.py --project-dir ~/.claude/skills/taxi-pipeline
```

- Reads `<dir>/openfused.toml` for the manifest (name defaults to directory basename).
- Materialises `<dir>/scripts/.venv` via `uv sync` on first run; subsequent runs reuse it.
- Available on `code run`, `code test`, and `code verify`; mutually exclusive with `--project`.

What both selectors do:
- Select the project's `.venv/bin/python` as the interpreter (all installed packages are available).
- Use a project-aware cache identity, so two runs of the same code against different lock files get separate cache entries.
- Local fan-out children (`_openfused.invoke` / `fused.map`) inherit the parent's project interpreter.

**Sharp edges:**
- `--project` / `--project-dir` are **local-only**. Passing them on an AWS or Fused environment raises a clear error.
- `code test` on the local backend **requires** a project selector, and pytest + coverage must be dev deps: `fused project add-dep <project> pytest coverage --dev`.
- **Stale project venv → auto-reconciled.** When the project's `uv.lock` is newer than its `.venv`, the local path runs `uv sync` once before executing. If the sync fails it runs on the stale venv, skips the cache, and prints a `warning:` line. Set `OPENFUSED_NO_VENV_SYNC=1` to disable auto-reconcile (CI / locked-down). `fused doctor` reports staleness without syncing.
- If the workspace project does not exist (`--project`), the error points at `fused project new <name>`. If the directory has no `openfused.toml` (`--project-dir`), you get a manifest-not-found error.

`boto3` is always present on AWS Lambda but may not be in a local venv — add it to the project if needed.

## Reading secrets inside UDF code

Use `openfused.get_secret(name)` — a uniform accessor that works unchanged on both
AWS and the local backend with no extra dependency declaration. Never interpolate
secret values into the code; that exposes them in logs and shell history.

Store the secret first (on AWS the name must carry the environment's function
prefix, e.g. `openfused-`, so the Lambda execution role can read it):

```sh
fused secrets put openfused-my-password    # prompts for the value; keeps it out of argv
```

Then read it inside the code:

```python
import openfused
import psycopg2

secret = openfused.get_secret("openfused-my-password")
conn = psycopg2.connect(password=secret, ...)
...
result = "done"
```

`get_secret` raises `KeyError` if the secret does not exist — never returns `None`.

**AWS** — the shim reads Secrets Manager directly via boto3 inside the Lambda
(execution-role scoped to `openfused-*`). **Local** — the shim dispatches through
the host invoke broker; the project venv needs neither `fused` nor `cryptography`
installed.

## Command sequence for a typical analysis

1. `fused files list --bucket … --prefix …` — find the input file
2. `fused files schema --bucket … --key …` — confirm columns / row count before running heavy code
3. `fused code run analysis.py` — run the analysis; write output to S3; return the output key
4. `fused files get --bucket … --key …` — mint a presigned URL for the output

## Parallel fan-out across partitions

When a task spans many partitions or files, don't loop sequentially. The right strategy depends on per-partition weight:

- **Light per-partition work** (counts, small aggregations) → a `ThreadPoolExecutor` inside a single `code run`.
- **Heavy per-partition work**, or a partition that would OOM or exceed `lambda_timeout` → fan out to child Lambdas with `fused.load(...).map(...)` / `_openfused.invoke` (see below).

Validate one worker call before dispatching the whole batch, batch oversized
partitions, and never fan out more than one level deep.

## Fused backend constraints

The Fused backend (`--backend fused`) runs code on a Fused-operated runtime and has
specific limitations:

- **No arbitrary packages** — only packages pre-baked into the runtime image are available (plus stdlib).
- **No `code test`** — the pytest harness is not available on the Fused runtime. Use the AWS or local backend to run tests.
- **Caching is Fused's own run cache**, not fused's content-addressed cache. `code run` still asks for its 1 h default (see **Caching**).
- **`--input-file` staging** — files are uploaded via the files API to `fd://tmp` and passed as a mapping of original filename → staged `fd://` path. For a **decorated UDF** (`@fused.udf def fn(...)`), the function must declare an `input_files` parameter. For a plain `result =` script, `input_files` is an in-scope variable. Filenames with path separators, `..`, or leading slashes are rejected as unsafe.
- **Batch compute mode** is not implemented; selecting it raises `NotImplementedError`.

## Monitoring

On the **AWS backend**, `code run` polls CloudWatch for the Lambda function while
the call runs and prints each snapshot to stderr (every `--monitor-interval`
seconds, default 10): concurrent executions, invocations, errors, throttles and
durations over the last 5 minutes, plus any warnings. CloudWatch lags ~1 minute, so
the current call may not be reflected yet.

**Read the warnings before running more code:**
- a concurrency spike — possible recursion runaway; stop and investigate
- `throttles > 0` — invocations were rejected due to concurrency limits
- `errors > 0` — function errors in the recent window (distinct from the current call's own error)

The **local** and **Fused** backends print no monitoring snapshots. There is no
flag to turn monitoring off.

## @fused.udf compatibility

Code that uses the `@fused.udf` decorator runs without modification. The handler
injects a `fused` mock module into every execution directory, so no real `fused`
package is required.

### How it works

The mock provides:

- **`@fused.udf`** — transparent decorator; the function is directly callable normally.
- **`@fused.udf(filename="worker.py")`** — same, but pins a default worker file for `.map()`.
- **`fused.load("worker")`** — returns a worker reference bound to a file (the `.py` is implied: `fused.load("worker")` loads `worker.py`). Call it (`worker(state="ak")`) to dispatch a single child Lambda, or use `.map()` to fan out. Not registered for auto-call. The file is not read until the worker is called or `.map()`'d.
- **`udf.map(items, filename=None, max_workers=16)`** — fans out to child Lambdas (see below).
- **`fused.run(udf_fn, **kwargs)`** — equivalent to `udf_fn(**kwargs)`; prefer calling directly.
- **`fused.Response(body, *, media_type, status_code=200, headers=None)`** and helpers **`fused.HTMLResponse` / `fused.PlainTextResponse` / `fused.JSONResponse`** — return one (as `result` or from a UDF) to set the HTTP content type/status/headers when the code is served via `fused code serve` or a share link. Any non-Response value is sent as JSON. Under `code run` it prints as `result (<media_type>, status N):` plus the body.

```python
import fused

@fused.udf
def resolution_frame(resolution=10):
    import pandas as pd
    return pd.DataFrame({"res": [resolution]})

result = resolution_frame(resolution=8)   # direct call — no fused.run() needed
```

### Fan-out with `.map()`

`udf.map(items, filename, max_workers=16)` dispatches one child Lambda per item using
`_openfused.invoke()` under the hood, collecting results in submission order.

```python
import fused

worker = fused.load("count_state")  # loads count_state.py; worker(state=...) dispatches one child; .map() fans out

@fused.udf
def coordinator(bucket=BUCKET, prefix=PREFIX, max_workers=51):
    states = list_states(bucket, prefix)
    results = worker.map(
        [{"state": s} for s in states],
        max_workers=max_workers,
    )
    return {"total": sum(r["rows"] for r in results)}
```

`items` is an iterable of dicts; each dict becomes the kwargs for one child invocation.
The child's `@fused.udf` receives those kwargs via the auto-call mechanism.

`filename` resolution order:
1. `filename` argument to `.map()`
2. `filename` argument to `@fused.udf(filename=...)`
3. `"user_code.py"` (the current execution's file inside Lambda)

**Per-child caching.** `_openfused.invoke(filename, …, cache_max_age="0s")` defaults
to **`"0s"`**: a child caches only when its own `invoke(...)` opts in, independently
of the parent — fanning out under a cached coordinator does not implicitly cache
the children.

### Auto-call behaviour

If the code defines a `@fused.udf` function but never assigns to `result`, the **last decorated function is called automatically** after the code block finishes. Arguments are loaded from `_openfused_args.json` in the working directory (populated by `_openfused.invoke()` kwargs) if that file exists; otherwise the UDF is called with no arguments.

```python
# No explicit result= needed — the UDF is auto-called with no args
import fused

@fused.udf
def compute():
    return 42
```

```python
# When invoked via _openfused.invoke("worker.py", x=10):
# _openfused_args.json contains {"x": 10}, so double_value(x=10) is called automatically.
import fused

@fused.udf
def double_value(x=0):
    return x * 2
```

### Rules

- **Direct call** — `udf(x=5)` works; no need for `fused.run(udf, x=5)`.
- **`result` and `@fused.udf` cannot coexist** — pick one return mechanism per script. Defining a `@fused.udf` and also assigning `result` (including `result = None`) is an **error**.
- **Only the last decorated function** is auto-called when multiple `@fused.udf` functions are defined (or name one with `--entrypoint`).
- **Errors in the UDF** (wrong argument count, runtime exception) appear on stderr like any other execution error.
- **`fused.py`** is a framework file and is not packed into child invocation zips; child Lambda invocations receive a fresh copy from the handler.

## What NOT to do

- Do not return a large DataFrame, dict, or list — serialize to Parquet/JSON and write to S3 instead
- Do not use `print` as a return mechanism — stdout is shown but is not a structured return channel
- Do not run multiple unrelated analyses in one `code run` — split them
- Do not fan out more than one level deep — workers must never invoke child Lambdas
- Do not rely on `code run` to scan or block code — it doesn't (see below)

## Verification and testing

`code run` executes code **without** any verify step: no spec check, no security
scan, no output firewall, no data-quality `expectations`, and no audit event. The
environment's verify settings have no effect on it. To scan first, run
`fused code verify` (optionally with `--spec`); to check behaviour, run
`fused code test`. Both are covered in **fused-verify**.

## Execution isolation & tenancy

Each `code run` executes in a fresh subprocess under a unique working dir, so module
state, monkeypatches, and files don't leak between calls. The **local** backend has
no isolation boundary beyond that — the code runs on your host as you. On the **AWS
backend**, every compute function is additionally created with **Lambda tenant
isolation mode**, and each call carries a *tenant id* so it runs in an execution
environment dedicated to that tenant:

- The tenant id is the caller identity from `OPENFUSED_CALLER_NAME` (free-form names are sanitized to Lambda's allowed character set). When it's unset, all calls share a single placeholder tenant (`openfused-shared`).
- Set distinct `OPENFUSED_CALLER_NAME` values per caller to keep mutually-distrusting workloads on separate warm-container pools. This isolates **compute only** — it does not scope the IAM role, so data isolation still needs a bucket-scoped role.

## Resetting the compute backend

Run `fused infra lambda-reset` to reset the resolved compute backend. Use this when:

- The backend is stuck in a broken state
- You need to force a fresh environment (e.g. after updating packages or handler logic)
- The local venv ready-cache or Lambda ARN cache has diverged from actual state

**AWS backend:** deletes all Lambda functions for the resolved environment, clears
the local ARN cache, and immediately recreates a fresh function so the next
`code run` is warm. The IAM role, ECR repository, and S3 cache bucket are **not**
affected.

**Local backend:** clears the in-process venv ready-cache. No venvs are deleted from
disk; the next `code run` re-checks the on-disk markers (and rebuilds anything
missing).

## Large results and caching

**Large results.** Return values too big for the 6 MB synchronous Lambda payload are
written to S3 and downloaded back transparently, so `result:` shows exactly what the
code returned. (Returning a large value is still the wrong pattern — write to S3
and return the key.)

**`code run` caches for 1 hour, with no flag to change it.** Every `code run`
memoizes its result for 1 h: a later run with the **same code, execution
environment, and input files** within the hour returns the stored stdout/stderr and
return value **without re-executing**. `code test` does not cache.

What that means in practice:
- The cache key is a content hash of the runner version, the execution environment
  (on AWS the container image **digest**; on local the venv identity), the code,
  and the input file bytes, scoped per environment.
- The key does **not** capture what the code reads at run time — S3 objects,
  secrets, `now()`, random numbers, network calls. Re-running unchanged code that
  reads live data within the hour returns the **old** result.
- There is no CLI flag to disable caching, force a refresh, or clear the cached
  entry. To get a fresh run, change the code (even a comment changes the hash) or
  the input files, or wait out the hour. Rebuilding the AWS image also changes the
  key.
- On the **Fused** backend the 1 h request goes to Fused's own run cache instead.
- The only cache-clear command in the CLI is `fused share cache-clear TOKEN`, which
  clears one share mount's cache — not `code run` results.

**Expiry of stored objects (AWS).** Cached entries live under `results/` in the
cache bucket (a lifecycle rule expires them after 30 days as a storage backstop);
one-shot large-result spills live under `spill/` (expired after 1 day). These rules
are provisioned by `fused infra apply`; see fused-infra.
