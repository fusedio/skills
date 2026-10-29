---
name: fused-beta
description: Call the team-built `fused.beta` methods — UDFs the Fused team wrote whose code stays on Fused's servers and whose calls run there — from Python (`fused.beta.{canvas}.{udf}(...)`), the CLI, or over HTTP (`POST /v1/tasks/run` with `task: "beta.{canvas}.{udf}"`, user or service-account token). Covers discovery with `fused workbench beta list|show`, `fused.beta.catalog()` and `GET /v1/beta/catalog`, the `TaskRun` handle for realtime and batch runs, and following a run to its result. Use when code mentions `fused.beta`, when asked to call a Fused team or beta UDF or method, or when starting beta tasks over HTTP.
---

# Calling `fused.beta` methods

> **CLI version:** commands below are written `fused workbench …` (only the 2.9.2b0+ pre-releases have this namespace; released versions such as 2.9.1 and 2.9.3 don't). If `fused workbench` fails with `No such command 'workbench'`, drop the word `workbench` — e.g. `fused beta list`. If `beta` itself is missing (`No such command 'beta'`), the installed fused predates the beta catalog: use `GET /v1/beta/catalog` over HTTP (below). See `fused-workbench-cli`.

`fused.beta` holds **UDFs built by the Fused team**. Each is a method like `fused.beta.example.hello(...)`, grouped by canvas (`example` is the canvas, `hello` the method). The UDF code is **not visible to you**: it stays on Fused's servers, and every call runs there. You only see each method's signature and docs.

Because the code is hidden, the signature and docs are the whole contract. Do not guess a method name, an argument name or a return shape. Do not decide a method does not exist because you cannot find it in the SDK or in the docs for other Fused APIs.

## Discover first

Always look up what exists before writing a call. Any of these gives the same catalog:

```bash
fused workbench beta list                    # every canvas and method, one line each
fused workbench beta show example            # one canvas, full docs
fused workbench beta show example.hello      # one method, full docs
fused workbench --format json beta show example.hello   # machine-readable
```

```python
print(fused.beta.catalog())                    # markdown, like `beta list`
print(fused.beta.catalog("example.hello"))     # one canvas or canvas.udf, full docs
fused.beta.catalog("example.hello", format="json")   # a dict
```

```
GET /v1/beta/catalog                           # JSON: {"canvases": [...]}
GET /v1/beta/catalog?name=example.hello&format=markdown
```

The `--format` flag goes before `beta`. An unknown name is an error (`ValueError` in Python, 404 over HTTP) that lists the known names.

Each canvas has a short description of when to use it. Each method has:

| Field | Meaning |
|---|---|
| `call` | The Python call path, `fused.beta.example.hello` |
| `task` | The name to run over HTTP, `beta.example.hello` |
| `signature` | Argument names, types and defaults. Use only these. |
| `summary`, `doc` | What it does, each argument, what it returns |

## The run handle

A call returns a `TaskRun` immediately; the work runs on the Fused server.

- **Realtime** (the default): `fused.beta.{canvas}.{udf}(...).wait().result()`. For runs of a few minutes at most.
- **Batch**: pass `engine="small"`, `"medium"` or `"large"`, then follow it with `run.tail()` (stream the logs) and read `run.result()`. No time limit.
- `fused.h3.get_run(id)` brings a run back by its `id`.
- `run.result()` returns what the UDF returned (a DataFrame, a dict, ...).

```python
import fused

run = fused.beta.example.hello(n=3)          # returns at once
df = run.wait().result()                      # realtime: block, then read the value

run = fused.beta.example.hello(n=3, engine="small")   # batch job
run.tail()                                    # follow the logs to the end
df = run.result()

run = fused.h3.get_run(run.id)                # later, from anywhere
```

Every generated method takes `engine=` as a keyword-only argument on top of the arguments in its signature.

## Calling over HTTP

Any caller can start the same tasks without the Python SDK. Base URL `https://www.fused.io/server` (or your deployment's `/server`).

Authenticate with one of:

- A user token: `Authorization: Bearer {user token}`. In Python get it with `fused.api.credentials.access_token()`.
- A service-account token: `Authorization: Fused-Service-Token {service-account-id}:{token}`. A service account's runs belong to its execution environment.

Start a run (returns 202 with the run, including its `id`):

    POST /v1/tasks/run
    {"task": "beta.{canvas}.{udf}", "args": {...}, "engine": "realtime"}

For example `{"task": "beta.example.hello", "args": {"n": 3}}`. `task` is the method's `task` name from the catalog, `args` are its arguments by name, and `engine` is `realtime` (default), `small`, `medium` or `large`. A batch run that would exceed the execution environment's quota is accepted and waits as `pending` until there is room.

Then follow it:

- `GET /v1/tasks/{id}`: `status` is `pending`, `running`, `succeeded` or `failed`.
- `GET /v1/tasks/{id}/logs`: the log lines.
- `GET /v1/tasks/{id}/result`: 202 while running. When ready it answers 204 with the output's presigned URL in the `x-fused-redirect` header and its type in `x-fused-content-type`. Fetch that URL **without** the Authorization header to get the bytes. Some deployments stream the output in the response body instead. 404 means the run failed or has no output.

Status codes on `POST /v1/tasks/run`: 404 unknown `task`, 422 invalid `args`, 400 unknown `engine`, 409 while another run of the same target is in progress.

### With a user token

```bash
BASE=https://www.fused.io/server
AUTH="Authorization: Bearer $FUSED_TOKEN"        # python -c "import fused; print(fused.api.credentials.access_token())"

ID=$(curl -s -X POST "$BASE/v1/tasks/run" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"task": "beta.example.hello", "args": {"n": 3}}' | jq -r .id)

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
  -d '{"task": "beta.example.hello", "args": {"n": 3}, "engine": "small"}' | jq -r .id)

curl -s "$BASE/v1/tasks/$ID" -H "$AUTH" | jq .status
curl -s -D - -o /dev/null "$BASE/v1/tasks/$ID/result" -H "$AUTH"   # 204 + x-fused-redirect
```

Fetch the `x-fused-redirect` URL without the header, as above. If the result response is 200 with a body instead of 204, read the body directly.

## Rules of thumb

- Run the catalog command first, and copy method and argument names from it.
- Read the method's `doc` for what it returns; the result's format follows the value the method returned, and `x-fused-content-type` names it (for example `application/json`, or a parquet or binary type for a table or file).
- Use `engine="small"` or larger for work that may take more than a few minutes; realtime runs are short.
- The catalog comes from the installed `fused` version or the deployed server, so it is always current for where you call.
