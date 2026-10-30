---
name: fused-beta
description: Call the team-built `fused.beta` methods — UDFs the Fused team wrote whose code stays on Fused's servers and whose calls run there — from Python (`fused.beta.{canvas}.{udf}(...)` or `fused.beta("canvas", "udf", ...)`), the CLI, or over HTTP (`POST /v1/tasks/run` with `task: "beta.run"`, user or service-account token). Covers discovery with `fused beta catalog`, `fused.beta.catalog()` and the public catalog JSON, the `TaskRun` handle for realtime and batch runs, `beta_version=` for an older published version, following a run to its result, trying a canvas directory locally with `fused.beta.local`, and the authoring rules a canvas must meet. Use when code mentions `fused.beta`, when asked to call a Fused team or beta UDF or method, when starting beta tasks over HTTP, or when writing a canvas for `fused.beta`.
---

# Calling `fused.beta` methods

`fused.beta` holds UDFs built by the Fused team, grouped by canvas: `fused.beta.example.hello(...)` is method `hello` of canvas `example`. The code stays on Fused's servers and every call runs there; the catalog's signature and docs are the whole contract. Never guess a method, an argument or a return shape: look it up first.

## Discover

```python
print(fused.beta.catalog())                    # every canvas, one line per method
print(fused.beta.catalog("example"))           # one canvas: version, published versions, README, full docs
print(fused.beta.catalog("example.hello"))     # one method, full docs and calling notes
fused.beta.catalog("example.hello", format="json")   # dict: {"canvases": [{name, version, versions, readme, methods: [{name, call, task, signature, summary, doc}]}]}
dir(fused.beta); dir(fused.beta.example)       # canvases; a canvas's methods
help(fused.beta)                               # the HTTP guide
```

CLI: `fused beta catalog [example[.hello]]`, `fused --format json beta catalog ...`, `fused beta skill ./skills/fused-beta` (writes a SKILL.md listing every method). The catalog JSON is public, no auth: `https://fused-asset.s3.us-west-2.amazonaws.com/.beta/catalog.json`. An unknown name is a `ValueError` (Python, CLI) listing the known ones; `fused.beta.nosuch` is an `AttributeError`.

In a signature, `Any` means the author gave no usable type and `= ...` a default the catalog cannot show; read `doc` for both.

## Call

Arguments are keyword-only. A call returns a `TaskRun` at once; the work runs on the server.

```python
import fused

df = fused.beta.example.hello(n=3).wait().result()          # realtime (default): short runs
run = fused.beta("example", "hello", n=3, engine="small")   # batch: "small", "medium" or "large", no time limit
run.tail()                                                  # stream the logs until the run ends
df = run.result()                                           # None while pending or running; never waits
run = fused.h3.get_run(run.id)                              # bring a run back later
fused.beta.example.hello(n=3, beta_version=2)               # an older published version; the catalog runs the current one
```

- `engine=` and `beta_version=` are keyword-only extras on every method.
- `result()` returns what the UDF returned (DataFrame, dict, ...). A failed run raises `RuntimeError` with the run's error.
- `fused.beta.local("./example")` loads a canvas directory (one `<udf>.py` per UDF, directory name = canvas name) and runs its UDFs in this process: `local.hello(n=3)` returns the value directly. Inside a UDF, published or local, `fused.load("other_udf")` by bare name resolves to the sibling UDF of the same canvas and version.

## HTTP

Base URL `https://www.fused.io/server` (or your deployment's `/server`). Auth header: `Authorization: Bearer {user token}` (Python: `fused.api.credentials.access_token()`) or `Authorization: Fused-Service-Token {service-account-id}:{token}`.

```
POST /v1/tasks/run  -> 202 with the run and its id
{"task": "beta.run", "args": {"canvas": "example", "udf": "hello", "args": {"n": 3}, "beta_version": 2}, "engine": "small"}
```

`args.args` are the method's arguments by name; `beta_version` is optional; `engine` is `realtime` (default), `small`, `medium` or `large`. Then `GET /v1/tasks/{id}` (`status`: `pending`, `running`, `succeeded`, `failed`; `error`), `GET /v1/tasks/{id}/logs`, and `GET /v1/tasks/{id}/result`: 202 while running; when ready, 204 with the output's presigned URL in `x-fused-redirect` (fetch it **without** the Authorization header) and its type in `x-fused-content-type`; some deployments stream the body instead. Errors on the POST: 404 unknown task, canvas or version (the message lists the published versions), 422 unknown udf or arguments off the signature, 400 unknown engine, 403 batch engine on a basic-tier plan. Full guide: `help(fused.beta)`.

## Publishing a canvas

Admin-only, from Workbench. A canvas is a directory of `<udf>.py` files plus a `README.md`; try it with `fused.beta.local` first. Each publish is a new version; older ones stay callable with `beta_version=`.

Blocks the publish (reported as `<udf>.py:<line>: <reason>`):

- Canvas name not a public Python identifier, or `catalog`/`local`; no UDFs.
- A `<udf>.py` that does not parse or does not hold exactly one `@fused.udf` function; a slug that is not a public identifier.
- A parameter that is positional-only, `*args` or `**kwargs`, named `engine`, `job_id`, `base_url`, `result_path`, `canvas`, `udf` or `beta_version`, or starting with `_` or `model_`.

Publishes with a warning (fix them: they are all a caller sees):

- Function named differently from its file; an `async` UDF.
- A parameter without an annotation, or one outside `str`, `int`, `float`, `bool`, `None`, `list[...]`, `dict[str, ...]`, `Literal[...]`, `X | None` (published as `Any`); a default that is not a JSON literal (shown as `= ...`).
- No return annotation; no docstring or one missing `Args:`, `Returns:` or `Example:`.
- No `README.md` or one without a first paragraph (it becomes the catalog summary).
