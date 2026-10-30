---
name: fused-beta
description: Call the team-built `fused.beta` methods — UDFs the Fused team wrote whose code stays on Fused's servers and whose calls run there — from Python (`fused.beta.{canvas}.{udf}(...)` or `fused.beta("canvas", "udf", ...)`), the CLI, or over HTTP (`POST /v1/tasks/run` with `task: "beta.run"`, user or service-account token). Covers discovery with `fused beta catalog`, `fused.beta.catalog()` and the public catalog JSON, the `TaskRun` handle for realtime and batch runs, following a run to its result, trying a canvas directory locally with `fused.beta.local`, and the authoring rules a canvas must meet. Use when code mentions `fused.beta`, when asked to call a Fused team or beta UDF or method, when starting beta tasks over HTTP, or when writing a canvas for `fused.beta`.
---

# Calling `fused.beta` methods

> **CLI version:** the commands below are `fused beta …`; `fused workbench beta …` is an alias that also works. If `fused beta` fails with `No such command 'beta'`, the installed fused predates the beta catalog: read the public catalog JSON (below) instead. See `fused-workbench-cli`.

`fused.beta` holds **UDFs built by the Fused team**. Each is a method like `fused.beta.example.hello(...)`, grouped by canvas (`example` is the canvas, `hello` the method). The UDF code is **not visible to you**: it stays on Fused's servers, and every call runs there. You only see each method's signature and docs.

Because the code is hidden, the signature and docs are the whole contract. Do not guess a method name, an argument name or a return shape. Do not decide a method does not exist because you cannot find it in the SDK or in the docs for other Fused APIs.

## Discover first

Always look up what exists before writing a call. Any of these gives the same catalog:

```bash
fused beta catalog                           # every canvas and method, one line each
fused beta catalog example                   # one canvas, full docs
fused beta catalog example.hello             # one method, full docs
fused --format json beta catalog example.hello   # machine-readable
fused beta skill ./skills/fused-beta         # writes SKILL.md there, listing every method
```

```python
print(fused.beta.catalog())                    # markdown, like `beta catalog`: one line per method
print(fused.beta.catalog("example.hello"))     # one canvas or canvas.udf, full docs
fused.beta.catalog("example.hello", format="json")   # a dict
help(fused.beta)                               # the HTTP API (the catalog itself does not repeat it)
dir(fused.beta); dir(fused.beta.example)       # the published canvases; a canvas's methods
```

```bash
curl -s https://fused-asset.s3.us-west-2.amazonaws.com/.beta/catalog.json   # public, no auth
```

The `--format` flag goes before `beta`. An unknown name is a `ValueError` in Python and the CLI that lists the known names; `fused.beta.nosuch` or `fused.beta.example.nosuch` is an `AttributeError`. The catalog JSON holds `{"canvases": {name: {version, summary, udfs: {udf: {signature, doc, ...}}}}}`, never code.

Each canvas has a short description of when to use it. In `fused.beta.catalog(format="json")` each method has:

| Field | Meaning |
|---|---|
| `call` | The Python call path, `fused.beta.example.hello` |
| `task` | The name to run over HTTP, always `beta.run` |
| `signature` | Argument names, types and defaults. Use only these. `Any` means the author gave no usable type; `= ...` means a default the catalog cannot show. Read `doc` for both. |
| `summary`, `doc` | What it does, each argument, what it returns |

## The run handle

A call returns a `TaskRun` immediately; the work runs on the Fused server. `fused.beta("example", "hello", n=3)` and `fused.beta.example.hello(n=3)` are the same call; arguments are keyword-only.

- **Realtime** (the default): `fused.beta.{canvas}.{udf}(...).wait().result()`. For runs of a few minutes at most.
- **Batch**: pass `engine="small"`, `"medium"` or `"large"`, then follow it with `run.tail()` (stream the logs, returns when the run ends) and read `run.result()`. No time limit. `result()` never waits: it returns None while the run is pending or running.
- `fused.h3.get_run(id)` brings a run back by its `id`.
- `run.result()` returns what the UDF returned (a DataFrame, a dict, ...).

```python
import fused

run = fused.beta.example.hello(n=3)          # returns at once
df = run.wait().result()                      # realtime: block, then read the value

run = fused.beta("example", "hello", n=3, engine="small")   # batch job, same call
run.tail()                                    # follow the logs to the end
df = run.result()

run = fused.h3.get_run(run.id)                # later, from anywhere
```

Every method takes `engine=` as a keyword-only argument on top of the arguments in its signature.

## Trying a canvas before it is published

`fused.beta.local("/path/to/canvas")` loads a canvas directory (one `<udf>.py` per UDF; the directory name is the canvas name) and runs its UDFs **in this process**, called the same way: `local = fused.beta.local("./example"); local.hello(n=3)` returns the value directly (no `TaskRun`, no `engine=`). `dir(local)` lists its UDFs. Inside a UDF, published or local, `fused.load("other_udf")` and `fused.run("other_udf")` by bare name resolve to the sibling UDF of the same canvas at the same version.

## Calling over HTTP

Any caller can start the same tasks without the Python SDK (the same guide is in `help(fused.beta)`). Base URL `https://www.fused.io/server` (or your deployment's `/server`); the paths below include the `/v1` prefix.

Authenticate with one of:

- A user token: `Authorization: Bearer {user token}`. In Python get it with `fused.api.credentials.access_token()`.
- A service-account token: `Authorization: Fused-Service-Token {service-account-id}:{token}`. A service account's runs belong to its execution environment.

Start a run (returns 202 with the run, including its `id`):

    POST /v1/tasks/run
    {"task": "beta.run", "args": {"canvas": "{canvas}", "udf": "{udf}", "args": {...}}, "engine": "realtime"}

For example `{"task": "beta.run", "args": {"canvas": "example", "udf": "hello", "args": {"n": 3}}}`. `task` is always `beta.run`; `args.canvas` and `args.udf` name the method and `args.args` are its arguments by name; `engine` is `realtime` (default), `small`, `medium` or `large`. A batch run that would exceed the execution environment's quota is accepted and waits as `pending` until there is room.

Then follow it:

- `GET /v1/tasks/{id}`: `status` is `pending`, `running`, `succeeded` or `failed`; `error` is the reason a failed run reports.
- `GET /v1/tasks/{id}/logs`: the log lines, oldest first.
- `GET /v1/tasks/{id}/result`: 202 while running. When ready it answers 204 with the output's presigned URL in the `x-fused-redirect` header and its type in `x-fused-content-type`. Fetch that URL **without** the Authorization header to get the bytes. Some deployments stream the output in the response body instead. 404 means the run failed or has no output.

Status codes on `POST /v1/tasks/run`: 404 for an unknown `task` or an unpublished `args.canvas`, 422 for an unknown `args.udf` or `args.args` that do not match the signature, 400 for an unknown `engine`, 403 when a basic-tier plan asks for a batch engine (realtime only).

### With a user token

```bash
BASE=https://www.fused.io/server
AUTH="Authorization: Bearer $FUSED_TOKEN"        # python -c "import fused; print(fused.api.credentials.access_token())"

ID=$(curl -s -X POST "$BASE/v1/tasks/run" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"task": "beta.run", "args": {"canvas": "example", "udf": "hello", "args": {"n": 3}}}' | jq -r .id)

curl -s "$BASE/v1/tasks/$ID" -H "$AUTH" | jq .status       # repeat until succeeded or failed
curl -s "$BASE/v1/tasks/$ID/logs" -H "$AUTH"

URL=$(curl -s -D - -o /dev/null "$BASE/v1/tasks/$ID/result" -H "$AUTH" \
  | tr -d '\r' | awk -F': ' 'tolower($1)=="x-fused-redirect"{print $2}')
curl -s "$URL"                                           # no Authorization header
```

### With a service-account token

Same calls; only the header changes.

```bash
BASE=https://www.fused.io/server
AUTH="Authorization: Fused-Service-Token $SERVICE_ACCOUNT_ID:$SERVICE_TOKEN"

ID=$(curl -s -X POST "$BASE/v1/tasks/run" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"task": "beta.run", "args": {"canvas": "example", "udf": "hello", "args": {"n": 3}}, "engine": "small"}' | jq -r .id)

curl -s "$BASE/v1/tasks/$ID" -H "$AUTH" | jq .status
curl -s -D - -o /dev/null "$BASE/v1/tasks/$ID/result" -H "$AUTH"   # 204 + x-fused-redirect
```

Fetch the `x-fused-redirect` URL without the header, as above. If the result response is 200 with a body instead of 204, read the body directly.

## Authoring a canvas for fused.beta

Publishing is admin-only, from Workbench (the `/v1/beta/canvas/{name}` endpoints behind it are not for callers). A canvas is a directory of `<udf>.py` files, ideally with a `README.md`; try it with `fused.beta.local` first. An ordinary canvas publishes as it is. Only the rules the runtime needs block a publish, reported as `<udf>.py:<line>: <reason>`:

- Canvas name: a Python identifier, not starting with `_`, not `catalog` or `local`. At least one UDF, each named as a public Python identifier.
- Each `<udf>.py`: parses, with exactly one `@fused.udf` function.
- Parameters: usable as keywords (no positional-only, `*args` or `**kwargs`); none named `engine`, `job_id`, `base_url`, `result_path`, `canvas` or `udf`, or starting with `_` or `model_`.

Everything else still publishes and comes back as a warning in the publish dialog. Fix them when you can, because they are the whole contract a caller or agent sees:

- `README.md` whose first paragraph says when to use the canvas (it becomes the catalog summary; without it the summary is empty).
- The function named like its file, not `async`.
- Every parameter annotated with `str`, `int`, `float`, `bool`, `None`, `list[...]`, `dict[str, ...]`, `Literal[...]` or `X | None` (not `typing.Optional`), with JSON-literal defaults. A parameter without such an annotation is published as `Any` (anything is accepted); a non-JSON default shows as `= ...` and the catalog cannot say what it is.
- A return annotation, and a docstring with `Args:`, `Returns:` and `Example:` sections.

## Rules of thumb

- Run the catalog command first, and copy method and argument names from it.
- Read the method's `doc` for what it returns; the result's format follows the value the method returned, and `x-fused-content-type` names it (for example `application/json`, or a parquet or binary type for a table or file).
- Use `engine="small"` or larger for work that may take more than a few minutes; realtime runs are short.
- The catalog is one public file shared by every deployment and cached for 60 s in the SDK, so what `fused beta catalog` prints is what the server runs.
