---
name: fused-storage
description: The fused storage and secrets CLI commands — inspecting cloud-native datasets and managing secrets. Use when finding/listing/counting S3 objects, reading a Parquet/Arrow/CSV schema, minting a download URL, uploading content, or storing/reading/deleting secrets, via `fused files list|count|get|schema|upload` and `fused secrets put|get|list|delete`. For running code over the data see fused-execute; for the full flag reference see fused-cli. If this is a step in building or running a project, load `fused-projects` first for the end-to-end model.
---

# Storage & secrets in fused

> **Part of the Fused skill set — don't work from it alone.** Fused is `workspace ⊃
> project ⊃ UDF`. If this is a step in building or running a project, load
> **`fused-projects`** for the end-to-end model and **`fused-execute`** for running
> code over the data. See **`fused-guide`** for the full set.

These commands are the **find → load → explore** front of the workflow: locate
data, understand its shape, and move bytes in/out — *before* you run code over it
with `fused code run`. They operate on the **resolved environment's** storage
backend — real S3 on AWS, the local filesystem on the local backend — so the same
commands work on either. Pass `--env NAME` (root option, before the group) to pick
an environment explicitly.

> These used to be MCP tools (`list_files`, `count_files`, `get_file`,
> `get_file_schema`, `upload_file`, `get_secret`, `put_secret`, `list_secrets`,
> `delete_secret`). The MCP server is gone; the CLI commands below are the
> replacement.

## Inspect before you compute

The cheapest way to avoid a wasted `code run` is to look first. Typical flow:
`files list` → `files count` → `files schema`, then write code against a known
schema.

### `fused files list [--bucket B] [--prefix P] [--page-size N]`

- **No `--bucket`** → lists buckets.
- **With `--bucket`** → lists keys under `--prefix`. The CLI **paginates
  automatically** and prints every key; `--page-size` only controls the request
  size.

```sh
fused files list                                   # what buckets exist?
fused files list --bucket my-data --prefix events/ # every key under events/
```

### `fused files count --bucket B [--prefix P] [--ext .parquet]…`

Counts objects under a prefix, optionally filtered by extension (repeat `--ext`) —
cheaper than listing all keys when you only need a tally.

```sh
fused files count --bucket my-data --prefix events/ --ext .parquet
```

### `fused files schema --bucket B --key K`

Column schema + metadata for a **Parquet, Arrow IPC, or CSV** file — read this to
learn column names/dtypes (and row count for Parquet/CSV) before writing a query.
Arrow IPC reports record-batch count rather than a row count. Requires pyarrow on
the host: install `fused[data]` (the `aws` extra includes it).

### `fused files get --bucket B --key K [--expires-in 3600]`

Prints a **presigned download URL** (default 1 h). On the local backend this is a
short-lived HMAC-signed `http://` URL served by a local file server, so it behaves
like the cloud path. Treat the URL as a bearer token — anyone with it can fetch the
object until it expires.

### `fused files upload [SRC] --bucket B --key K`

Uploads a local file, or stdin when `SRC` is omitted:

```sh
fused files upload ./sample.csv --bucket my-data --key samples/sample.csv
some-command | fused files upload --bucket my-data --key out/result.json
```

For large or computed outputs, prefer writing **from inside `fused code run`** (the
code has direct S3 access via the execution role) rather than round-tripping bytes
through the host — see fused-execute.

## Secrets

Secrets let executing code reach databases/APIs without hard-coding credentials.
The model is **the execution principal reads the store directly** — values are
never injected into the code payload.

**Never put a secret value on the command line** (it lands in shell history and the
process list). Use the prompt or a pipe/file:

```sh
fused secrets put openfused-pg-conn                        # prompts, no echo
printf '%s' "$PG_CONN" | fused secrets put openfused-pg-conn --value-file -
fused secrets put openfused-pg-conn --value-file ./pg-conn.txt
```

### Mind the name prefix (AWS)

On AWS the Lambda execution role can only read secrets under the environment's
`function_prefix` (e.g. `openfused-*`). `secrets put` **enforces this at write
time**: a name outside the prefix is rejected with an actionable error rather than
becoming an invisible-at-runtime secret. So name secrets `openfused-<thing>`.

Then read it *inside* the execution using `openfused.get_secret` — works on both
AWS and the local backend; it raises `KeyError` when the secret is absent:

```python
import openfused

conn = openfused.get_secret("openfused-pg-conn")
result = ...  # use conn
```

(`examples/duckdb_with_secret.py` is a full DuckDB-over-Postgres example.)

### `fused secrets get NAME` / `fused secrets list [--prefix P]`

`get` prints the secret string (errors if absent or binary — text only). `list`
prints names, prefix-filtered. On the local backend secrets live in the OS keychain
(one JSON blob per environment, keyed by the resolved store path); access control
is OS-keychain, not IAM.

> **Linux/WSL has no native keychain.** Where no usable OS keychain exists, every
> local secret operation **raises a `RuntimeError`** naming both remedies: install
> the file-based fallback (`fused[local]`, which pulls in `keyrings.alt` and stores
> secrets *unencrypted* on disk — dev only) or switch to the AWS backend for
> headless/CI use.

### `fused secrets delete NAME [--yes]`

Prompts for confirmation (`--yes` skips it). On AWS the secret is **scheduled**
for deletion with the default 30-day recovery window (recoverable via AWS tooling
until it elapses); on the local backend the name is removed from the keychain map
immediately. Do not "delete" by overwriting with an empty value — that leaves a
readable (empty) secret in place.

## Notes

- There is no CLI command for clearing cached/spilled `code run` results. The only
  cache-clear command is `fused share cache-clear TOKEN`, which clears one share
  mount's cache (see fused-cli).
- Full flag reference: fused-cli.
