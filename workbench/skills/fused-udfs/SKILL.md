---
name: fused-udfs
description: Comprehensive guide for writing Fused User Defined Functions (UDFs). Use when helping users create, optimize, or debug UDFs, including function structure, parameter handling, performance optimization, agent-friendly design, and security best practices.
---

# Writing Fused UDFs

Reference docs.fused.io for the most up-to-date information.

**📖 References:** [UDF Writing Guide](https://docs.fused.io/guide/working-with-udfs/writing-udfs/) | [UDF Best Practices](https://docs.fused.io/user-guide/best-practices/udf-best-practices/) | [Getting Started](https://docs.fused.io/guide/getting-started/first-udf-basics/)

## Function Structure & Decorators

### Basic UDF Pattern
```python
@fused.udf
def udf(bounds: fused.types.Bounds = None, name: str = "Fused"):
    import pandas as pd
    return pd.DataFrame({'message': [f'Hello {name}!']})
```

> **All imports must be inside the UDF function body.** Unlike regular Python, imports at module level are not executed — only the decorated function runs in the Fused runtime. Put every `import` statement inside `def udf(...)`:
>
> ```python
> # ✗ Wrong — module-level import, will not be available
> import pandas as pd
>
> @fused.udf
> def udf():
>     return pd.DataFrame(...)  # NameError: pd not defined
>
> # ✓ Correct
> @fused.udf
> def udf():
>     import pandas as pd
>     return pd.DataFrame(...)
> ```

### @fused.udf Parameters
- `cache_max_age`: Control caching duration (`"30s"`, `"10m"`, `"24h"`, `"7d"`). Use `cache_max_age=0` if it is important that the UDF always be rerun, for example if it reads something that will not be part of the cache key. The cache key will be the parameters it is called with.

> **`cache_max_age=0` is mandatory for UDFs with side effects.** If a UDF creates a Notion ticket, sends a message, writes to a database, or performs any other write, omitting `cache_max_age=0` means a second call with the same parameters returns the cached result silently — the write never happens. Always set `cache_max_age=0` on any UDF that produces output beyond its return value:
>
> ```python
> @fused.udf(cache_max_age=0)   # ← required — creates a ticket every call
> def udf(title: str = "Bug report", description: str = ""):
>     nt = fused.api.notion_connect()
>     client = nt.client()
>     client.pages.create(...)
> ```

## Parameter Handling & Types

**📖 Reference:** [UDF Editor](https://docs.fused.io/workbench/udf-editor/)

### Type Annotations
UDFs resolve parameters to annotated types:
```python
import geopandas as gpd
import pandas as pd

@fused.udf
def udf(
    bounds: fused.types.Bounds = None,
    gdf: gpd.GeoDataFrame = None,
    df: pd.DataFrame = None,
    name: str = "default",
    count: int = 100,
    flag: bool = True
):
    # Function body
```

### Agent-Friendly Defaults
Provide sensible defaults so agents can call UDFs without specifying every parameter:
```python
@fused.udf
def get_data(bounds: fused.types.Bounds = None, year: int = 2020, limit: int = 1000):
    """Agent can call with just bounds if needed."""
```

> **`fused.types.Bounds = None` means the UDF cannot run standalone.** When `bounds` defaults to `None`, the UDF expects a caller (map viewport, widget, or another UDF) to supply the bbox. If you want to run the UDF with `fused workbench run` or call it without arguments, provide a concrete default bbox instead:
>
> ```python
> # ✗ Cannot run standalone — fused workbench run will fail with no bounds
> def udf(bounds: fused.types.Bounds = None): ...
>
> # ✓ Runs standalone with the default; still overridable by map viewport
> def udf(bounds: fused.types.Bounds = [-122.5, 37.7, -122.3, 37.9]): ...
> ```

## Return Types

**📖 Reference:** [Write UDFs](https://docs.fused.io/core-concepts/write/)

UDFs can return:
- `pd.DataFrame`, `pd.Series`
- `gpd.GeoDataFrame`, `gpd.GeoSeries`
- `shapely.Geometry`
- Arrays (must be 2D or higher)
- `str` — rendered as HTML in the workbench. This is what an HTML template node's `{{udf}}` or a JSON-UI `iframe` widget's `src: "{{udf}}"` inlines verbatim (folium maps, plotly `fig.to_html()`, Jinja output).

### UDFs called from HTML template nodes

When a canvas HTML node calls a UDF with `await fused.runPython("my_udf", {n: 5, bbox: [..]})` (see the `workbench:html-template-nodes` skill):
- Every value arrives as a **string** (non-strings JSON-encoded). Annotate parameters (`n: int`, `bbox: list`, `flag: bool`) so they coerce; an unannotated `n` is `"5"`.
- Return a DataFrame with JSON-friendly columns (no raw geometry objects, timestamps as ISO strings). The page receives an array of row objects.
- Include an identifier column when the page will join or key rows.
- The HTML node needs an edge from this UDF in `canvas.toml`, or the call is rejected with `not_allowed`.

```python
# DataFrame return
return pd.DataFrame({'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']})

# GeoDataFrame return
gdf = gpd.GeoDataFrame({
    'geometry': [Point(0, 0), Point(1, 1)],
    'value': [10, 20]
})
return gdf
```

### Cross-UDF Loading
For loading a UDF that is defined in the same canvas, specify its name:
```python
@fused.udf
def udf():
    common = fused.load("my_other_udf")
    return common.some_function()
```

For loading a UDF from GitHub, prefer specifying its Git SHA. Prefer using the latest Git SHA - do not guess an SHA - in the following format:
```python
@fused.udf
def udf():
    common = fused.load("https://github.com/fusedio/udfs/tree/******/public/common/")
    return common.some_function()
```

## Parallelism with `udf.map()`

`udf.map()` is Fused's native fan-out: it launches N simultaneous serverless jobs, one per item in the list, without needing a dedicated instance. Use this instead of `engine="medium"` for embarrassingly parallel workloads — dedicated instances take ~30s to start, while `udf.map()` on the default engine is nearly instant.

```python
@fused.udf
def udf(items: list = ["a", "b", "c"]):
    # Load the sibling UDF that will run in parallel
    worker = fused.load("my_worker_udf")

    # Map over items — each becomes a separate serverless call
    results = worker.map(items, shared_param="value").df()
    return results
```

- The first argument to `.map()` is the list to iterate over — each element is passed as the worker UDF's **first positional parameter**.
- Additional kwargs are **shared** across all invocations (same value for every call).
- `.df()` blocks until all jobs complete and concatenates their DataFrames.
- Workers don't receive an index automatically — if each job needs a unique ID, derive it from the item itself rather than relying on a default parameter.
- **Pass results back via DataFrame columns, not intermediate files.** Workers should return their output (bytes, JSON, computed values) as columns in the returned DataFrame. Writing to S3 and reading back from parallel workers introduces credential and timing issues; returning data directly is simpler and more reliable.

**Worker + orchestrator pattern.** The idiomatic way to build a parallelisable canvas is to keep the per-item UDF standalone and add a separate orchestrator that fans out over a list. The worker UDF must echo the item it processed back as a column so the concatenated result stays attributable:

```python
# Worker UDF: handles one item, always works standalone
@fused.udf
def udf(item: str = "default"):
    import pandas as pd
    result_df = compute(item)
    result_df['item'] = item  # ← always include — required after concat
    return result_df

# Orchestrator UDF: generates the list and maps
@fused.udf
def udf(items_csv: str = "a,b,c"):
    worker = fused.load("worker_udf")
    items = [x.strip() for x in items_csv.split(",")]
    return worker.map(items).df()
```

This pattern gives you two working nodes in the canvas: the worker for single-item debugging and the orchestrator for the full parallel run. Design the worker first; the orchestrator is always a thin wrapper.

## Performance Optimization

**📖 Reference:** [Scaling Out UDFs](https://docs.fused.io/guide/working-with-udfs/udf-best-practices/scaling-out/)

### @fused.cache Decorator
Cache expensive operations to improve performance:
```python
@fused.udf
def udf(data_path: str):
    import pandas as pd
    
    @fused.cache  # Persist across runs
    def load_data(path):
        return pd.read_csv(path)  # Slow operation
    
    @fused.cache(cache_max_age='1h')  # Time-limited cache
    def process_data(df):
        return df.groupby('category').sum()
    
    df = load_data(data_path)
    return process_data(df)
```

> **`@fused.cache` on inner functions caches failures too.** If a `@fused.cache`-decorated inner function fails — returns `None`, raises an exception, or gets a bad response from an external API — that failure result is stored and returned on every subsequent call with the same arguments, forever, until the cache key changes. Setting `cache_max_age=0` on the outer `@fused.udf` does **not** bust inner `@fused.cache` entries; they have their own persistent storage keyed only on the function arguments.
>
> The standard fix is a `_v` version parameter. Bump it whenever you need to force fresh execution:
>
> ```python
> @fused.cache
> def fetch_from_api(key, _v=1):
>     result = external_api_call(key)
>     return result  # None/error stays cached until _v changes
>
> # After fixing the underlying issue, bump _v to bust the stale entry:
> @fused.cache
> def fetch_from_api(key, _v=2):
>     ...
> ```
>
> This comes up most often when an external API call fails during development (rate limit, bad credentials, temporary outage) — the failure gets cached, and even after fixing the issue the UDF keeps returning the stale `None`. The outer `@fused.udf(cache_max_age=0)` only clears the UDF-level result cache, not the inner function's cache.

### Performance Guidelines
- Keep UDFs short and fast (aim for 30-45 seconds, timeout at 120 seconds)
- Use caching for expensive operations
- Cache data loading, not business logic that changes frequently
- Consider hierarchical caching for complex pipelines

## Cache Invalidation

**📖 Reference:** [Cache Invalidation](https://docs.fused.io/guide/working-with-udfs/udf-best-practices/cache-invalidation/)

Fused caches UDF results automatically. Invalidate the cache when source data changes, after fixing a UDF bug, or as part of a redeploy — otherwise callers will keep getting the stale result.

### `invalidate_cache()` from Python

Call `invalidate_cache()` on a loaded UDF object. With no arguments it clears every cached result for that UDF:

```python
@fused.udf
def udf():
    parent = fused.load("udf_to_invalidate")
    parent.invalidate_cache()
    return parent()
```

For Tile UDFs, pass `z`, `x`, `y` to invalidate a single tile. **All three parameters are required together** — partial tile specs are rejected:

```python
udf = fused.load("udf_to_invalidate")
udf.invalidate_cache(z=15, x=9647, y=12320)
```

### HTTP API for external automation

For CI/CD, cron jobs, or anything outside a UDF, use the REST endpoint with a service token:

```
DELETE https://www.fused.io/server/v1/realtime-shared/{client_id}/udf-cache/by-id/{udf_id}/delete
```

Get the identifiers from the SDK:

- `udf_id` → `fused.load(...).metadata["fused:id"]`
- `client_id` → `fused.options.realtime_client_id`

Append `z`, `x`, `y` query params to invalidate a single tile (all three required, or the server returns 422). Store service tokens as environment variables — never inline them in code.

## Code Organization

**📖 Reference:** [Storage Options](https://docs.fused.io/guide/working-with-udfs/udf-best-practices/storage/)

### Business Logic Focus
Keep only essential business logic in the decorated function. Extract complex operations to utils or separate functions.

## Agent-Friendly Design

**📖 Reference:** [Building UDFs for Agents](https://docs.fused.io/guide/working-with-udfs/udf-best-practices/agents/)

### Docstrings as tool descriptions

When a canvas is used as an LLM tool backend (via the canvas bot or MCP), the UDF's docstring becomes the tool description the model reads to decide *when* and *how* to call it. **The docstring must say when to call the UDF, not just what it does.**

```python
# ✗ Describes what — doesn't tell the LLM when to use it
def udf(title: str, description: str):
    """Creates a page in the Notion Engineering Tasks database."""

# ✓ Describes when — LLM knows to call this on any bug report
@fused.udf(cache_max_age=0)
def udf(title: str = "Bug report", description: str = "", is_severe: bool = False):
    """
    Creates a bug ticket in the Fused Engineering Tasks Notion database.

    Call this whenever a user reports:
    - Something in Fused not working as expected
    - Unexpected errors or broken behavior
    - Missing, incorrect, or confusing documentation

    Always call this in addition to answering the user's question — do not
    skip it when a bug or docs issue is detected.

    Set is_severe=True if the bug completely blocks the user from using Fused,
    causes data loss, or sounds like a critical production failure.
    Leave is_severe=False for minor issues, docs gaps, or unclear severity.
    """
```

### Naming: UDF name and parameter names are the first thing the agent sees

The agent reads the tool name and parameter names before the docstring. Name them so the intent is unambiguous without reading any further.

**UDF (file) name** — use a verb phrase that describes the action and its side effect:

```
# ✗ Ambiguous — does this return data, save it, or display it?
process_data       export_report       run_model

# ✓ Unambiguous — action + destination makes the side effect explicit
process_and_save_to_s3     export_report_to_google_drive     run_model_and_return_scores
```

**Parameter names** — encode type, direction, and format, not just the value:

```python
# ✗ Ambiguous — input or output? local or S3? folder or file?
def udf(path: str, output: str, file: str): ...

# ✓ Unambiguous at a glance
def udf(input_csv_s3_path: str, output_s3_folder: str, output_filename: str): ...
```

Rules of thumb:
- Prefix with `input_` or `output_` to signal direction
- Suffix with `_s3_path`, `_s3_folder`, `_url`, `_local_path` to signal location/format
- Avoid abbreviations: `num_results` → `number_of_results`, `fmt` → `output_format`
- For flags, name the true case: `overwrite_existing` is clearer than `force`

### Design principles for LLM-callable UDFs

- **Simple parameter types** — use `str`, `int`, `bool`. Avoid complex objects; the LLM constructs arguments from the docstring description and can't build nested structures reliably.
- **Meaningful return columns** — the LLM reads the tool result, so `{"status": "saved", "output_s3_path": "s3://..."}` is useful feedback; an unlabelled array is not.
- **One action per UDF** — an LLM tool that "searches docs and creates a ticket if needed" is harder to invoke correctly than two separate tools. Keep each UDF focused.
- **`cache_max_age=0` on all write UDFs** — see the note above; silent cache hits are a common failure mode for ticket-creation and notification UDFs.

## Security Best Practices

**📖 Reference:** [Security](https://docs.fused.io/guide/working-with-udfs/udf-best-practices/security/)

### Secrets

**📖 Reference:** [Secrets management](https://docs.fused.io/guide/advanced-setup/secrets-management)

- Never put secrets in UDF code. Always store them in secrets or use integrations.

### Input Validation
```python
@fused.udf
def secure_udf(user_input: str, file_name: str):
    from pathlib import Path
    import pandas as pd
    
    # Validate inputs
    if not user_input or len(user_input) > 1000:
        return pd.DataFrame({'error': ['Invalid input length']})

    # Validate filename format before path resolution
    if not file_name or file_name.startswith(('/', '\\')):
        return pd.DataFrame({'error': ['Invalid file path']})

    allowed_dir = Path('/allowed/directory').resolve()
    safe_path = (allowed_dir / file_name).resolve()

    # Defense in depth: enforce directory containment
    if allowed_dir not in safe_path.parents:
        return pd.DataFrame({'error': ['Invalid file path']})

    return pd.read_csv(safe_path)
```

### Never Accept From Agents
- Free-form SQL queries
- Table names
- Absolute file paths or traversal sequences (`..`)
- System commands
- Python code to be `eval`'d.

All agent-supplied parameters should be treated as untrusted input.
If dynamic file names are required, resolve and validate the full path before use.

## Testing UDFs

**📖 Reference:** [Small UDF Run](https://docs.fused.io/core-concepts/run-udfs/run-small-udfs/), see also the `fused-cli` skill

**Always run the UDF after writing it** — don't stop at pushing the code. UDFs fail in ways static analysis can't catch: wrong parameter types, missing data, unexpected runtime behaviour. A passing push is not a passing test.

```bash
# Basic run
fused workbench run CANVAS_NAME udf_name

# With a parameter
fused workbench run CANVAS_NAME udf_name --param=value

# Force fresh execution (skip cache)
fused workbench run CANVAS_NAME udf_name --cache-max-age=0

# Profile performance
fused workbench run CANVAS_NAME udf_name --profile
```

**What counts as passing:** any non-error return. An empty `{}` or `None` is fine if the data source isn't populated yet — what matters is no exception. If the UDF has a `date` or `id` parameter, test with a real value that should have data.

**Start with a smoke test.** When writing a new UDF — especially one that connects to an external service — verify the connection returns data before building the full logic. This separates "can I connect?" from "does my logic work?", and makes failures much easier to diagnose.

- `fused workbench json-ui validate <file>` - Validate widget configs before pushing

> **`fused workbench run` always executes the deployed remote version, not your local files.** If you edit a UDF and immediately run `fused workbench run canvas_name udf_name`, you will get the previously deployed version — the CLI prints `"UDF '...' returned cached result"` which can make this easy to miss. Always push first:
>
> ```bash
> # Edit → push → run (correct order)
> fused workbench canvas push ./my_canvas --canvas my_canvas
> fused workbench run my_canvas my_udf --param=value
> ```
>
> Alternatively, pass the local `.py` file directly to run without pushing — but note that `fused.secrets` and `fused.api` integrations are only available in the remote runtime:
>
> ```bash
> fused workbench run my_canvas ./my_canvas/my_udf.py --param=value
> ```
