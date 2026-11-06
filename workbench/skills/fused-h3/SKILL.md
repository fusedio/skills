---
name: fused-h3
description: Ingest data into H3 hex datasets and query them with the `fused.h3` API. Covers partitioning points, geometries, gridded rasters (ERA5-style) or tables that already carry an H3 column into hex-sorted Parquet as server-side runs, checking a large or messy Parquet folder first with `fused.h3.inspect`, registering the output with `fused.h3.index` (whole tree, some partition folders, a flat folder in file batches, or fanned out over several instances), and reading it back with `fused.h3.query` inside a UDF. Also covers the published ERA5 and GridMET hex datasets. Use when converting data to H3, building, adding to or redoing a hex dataset, following or retrying a partition/index run, querying one by point/bbox/cell/time/partition, or reading ERA5/GridMET weather by location. Also use when showing a hex dataset on a map or visualising it (the `fused-map` `fused-hex` layer, zoomed-out overviews, `chunk_res_offset`), or calling `/h3/query` directly from a widget or HTML page.
---

# H3 ingestion with `fused.h3`

`fused.h3` turns tabular data into a **hex dataset**: Parquet files sorted by a uint64 `hex` column, one file per coarse parent cell, described by a `_manifest.json`. Once **indexed**, the dataset is queryable by point, bbox, cell, time and partition values without scanning every file.

The workflow is always:

1. **Source**: describe the input with `fused.h3.sources.parquet`, `.era5` or `.udf` (or pass a cloud Parquet path). For a big folder of Parquet, run `fused.h3.inspect(path)` first.
2. **Partition**: `fused.h3.partition(...)` starts a server-side run that writes the hex dataset and returns a `Run`.
3. **Index**: `fused.h3.index(path, ...)` starts a server-side run that registers it and returns a `TaskRun`.
4. **Query**: `fused.h3.query(path, ...)` returns a DataFrame. It only runs inside a UDF on Fused.

`partition` and `index` work from anywhere the `fused` SDK is authenticated: a notebook, a script, or a UDF. Nothing is read or uploaded from the calling machine. They send a description of the work to the Fused server and **return as soon as the run has started**. Call `run.tail()` to follow it to the end. `inspect` is the exception: it reads on your machine with your local credentials.

For the published ERA5 and GridMET hex datasets (read-only, no ingestion needed), see [`datasets.md`](datasets.md).

To show an indexed dataset on a map, or call `/h3/query` from a widget, see [`map.md`](map.md).

## Choosing how rows get a hex

`partition` needs exactly one of `hex_column=` or `point_column=`:

| Your data | Call |
|---|---|
| Already has an **integer** H3 column | `hex_column="h3"`, with `h3_res` set to that column's resolution. It is cast to uint64 and **renamed to `hex`** in the output. Convert string ids first: `df["h3"] = df["h3"].map(h3.str_to_int)`. |
| lat/lng columns | `point_column=("lat", "lng")`, lat first |
| A WKB geometry column (GeoDataFrame) | `point_column="geometry"`. Points hex themselves; other shapes get the cell of their planar centroid. One row in, one row out: polygons are **not** polyfilled. |
| A regular lat/lng raster (grid of values, e.g. 0.25° climate data) that should cover **every** cell | `point_column=("lat", "lng"), fill="nearest"`. Each cell at `h3_res` takes the nearest raster point's values. |

Coordinates must be EPSG:4326 degrees. Nothing is reprojected, and projected values (UTM metres, say) fail the run. Geometries crossing the antimeridian or wrapping a pole get a wrong planar centroid: split them, or pass lat/lng.

A null point (null or NaN lat/lng, or a null geometry) fails the job by default. `on_null_point="drop"` skips those rows instead and records the count in the job log and in the manifest as `rows_dropped_null_point`. Out-of-range values always fail.

## Sources

`data` must be a `fused.h3.sources` source, or a `s3://` / `gs://` / `gcs://` / `fd://` / `/mount/<folder>` path, which means `sources.parquet(path)`. A DataFrame, Arrow table, record-batch iterator, xarray dataset, local path, `memory://` or `az://` path raises `TypeError`. To partition data you hold in Python, return it from a UDF and pass `sources.udf(...)`.

```python
fused.h3.sources.parquet(path, *, columns=None, batch_size=65_536, schema=None,
                         filter=None, read_threads=1, **hive_keys)
fused.h3.sources.era5(*, outputs, month=None, date=None, cadence="daily",
                      bbox=None, read_workers=16)
fused.h3.sources.udf(udf, **fixed)
```

| Source | Use |
|---|---|
| `parquet` | One Parquet file or every `.parquet` under a folder (recursive, sorted). Details below. |
| `era5` | ERA5 from Google's public ARCO Zarr as `lat, lng, month, date[, hour], <outputs…>` batches, ready for `fill="nearest"`. Give exactly one of `month="YYYY-MM"` or `date="YYYY-MM-DD"`, here or per job in `partition_by`. Daily outputs include `t2m_min/max/mean`, `tp`, `d2m`, `sp`, `u10`, `v10`, `ssrd`, soil layers; hourly uses `t2m`. `bbox=(min_lng, min_lat, max_lng, max_lat)` trims memory and output but not download. |
| `udf` | Runs a `@fused.udf` on the server, once per job. Its parameters are the source's inputs, and it must **return** a DataFrame, GeoDataFrame, Arrow `Table` or `RecordBatch`, not a generator. The UDF is serialized, so import inside its body and don't rely on local files or variables. GeoDataFrame geometry arrives as WKB. |

### `sources.parquet` options

- `columns=`: read only these columns.
- `schema=`: by default the schema is unified from every file's footer. A column typed `null` in one file and `string` in another reads as `string`, integers widen, and a column missing from a file reads as nulls. Types that can't be unified (int in one file, string in another) raise and ask for `schema=`. A given `pyarrow.Schema` replaces the unification: it lists the columns read, and values are cast to it.
- `filter=`: pyarrow DNF filters, as `pq.read_table(filters=)` takes. A list of `(column, op, value)` tuples ANDs them; a list of such lists ORs the groups. `op` is `==`, `!=`, `<`, `>`, `<=`, `>=`, `in`, `not in`, with plain scalar values. Row groups whose footer stats rule them out are skipped. The filter columns don't have to be in `columns=`.
- `read_threads=`: read this many files at once (default 1, in path order). With more, batches from different files interleave. Use it for many small files or high-latency storage; each thread holds a few batches in memory.
- `**hive_keys`: `year=2020` reads `<path>/year=2020/` and adds `year` as a string column when the files lack it.

### `sources.udf(udf, **fixed)`

`fixed` keywords are values that are the same for every job, usually from the caller's scope: `sources.udf(read_month, bucket=bucket)`. They are stored in the source's spec and sent with the code in plain text, so **never pass secrets**; read those inside the UDF with `fused.secrets`. Changing a fixed value changes the jobs' read-cache folders, so the jobs are read again. Fixed values are not part of job ids or partition values. A name the UDF doesn't take raises (unless it takes `**kwargs`), and so does a name that is also a `partition_by` key.

Values that differ between jobs go in `partition_by={...}`. Don't combine `partition_by` jobs with a source that already has inputs (`.bind(...)`, or `month=` given to `era5`): that raises.

### Read step for `udf` and `era5`

A `udf` or `era5` source is read first by an `h3.read` batch job per job on `read_engine` (default `"small"`). It caches the rows under `<output>/.fused-h3-source/`, and the partition job starts once the read succeeds. `run.tail()` prints `[job] reading the source` and then `[job] partitioning`. A re-run reuses the cache for an unchanged job (same source, inputs, fixed values and UDF code). `redo=True` reads again. A `parquet` source has no read step.

## Partition

```python
run = fused.h3.partition(
    data,                      # a fused.h3.sources source, or an s3:// / gs:// / fd:// / /mount Parquet path
    output,                    # "fd://...", "s3://bucket/prefix/", "gs://..." or "/mount/<folder>"; not local, not az://
    *,
    hex_column=None, point_column=None,
    h3_res=7,                  # resolution of the `hex` column (one row per cell per key)
    file_res=1,                # parent resolution that groups rows into files
    fill=None,                 # None | "nearest"
    partition_by=None,         # column(s) from the data, or {column: [values]} for one job per value
    sort_by=None,              # secondary sort inside each file, after `hex`
    redo=False,                # redo what this call covers (see below)
    chunk_res_offset=None,     # align row groups to parent cells at file_res + offset
    on_null_point="raise",     # "raise" | "drop"
    read_engine="small",       # batch instance for udf/era5 read jobs
    engine="small",            # partition job: batch instance, or "realtime" (parquet sources only)
    options=None,              # tuning dict, below
) -> fused.h3.Run
```

`options` keys (an unknown key raises):

| Key | Default |
|---|---|
| `row_group_size` | 65 536 rows; not allowed with `chunk_res_offset` |
| `compression`, `compression_level` | `"zstd"`, 5 |
| `key_columns` | dictionary-encoded columns; defaults to the `partition_by` columns |
| `memory_budget` | bytes of buffered rows before spilling; a quarter of the instance's RAM (at least 1 GiB) |
| `workers` | file-writer threads; up to 32, cut so each thread can hold the largest output file in RAM. An explicit value is used as given. |

**Output layout:** `<output>/<col>=<value>/.../<file_res parent cell>.parquet` plus `<output>/_manifest.json`. Each file holds `hex` (uint64) and every input column, sorted by `hex` then `sort_by`. Point and geometry columns are kept.

**Resolutions:** `0 <= file_res <= h3_res <= 15`. `file_res=1` (842 global parents) is what the ERA5/GridMET datasets use at res 7. For finer `h3_res` or regional data, raise `file_res` so each file holds a manageable number of rows.

**`chunk_res_offset`:** every row group holds whole cells at `file_res + chunk_res_offset`, about `7**offset` row groups per file (3 gives about 343). Needs `file_res + chunk_res_offset <= h3_res`. It lets a map draw a zoomed-out overview of the values; see [`map.md`](map.md).

**`partition_by` values** become folder names: dates as `YYYY-MM-DD`, timestamps as ISO, ints as digits. Values must be non-null, non-empty, not start with `_`, and contain no `/`.

**Engines:** the partition job runs as a `"small"` batch job by default, with no time limit. Pass `"medium"`, `"large"`, … for a bigger instance. `engine="realtime"` is limited to a few minutes and only suits small Parquet inputs: a `udf` or `era5` source raises with it. `read_engine` must be a batch instance; raise it for a UDF or ERA5 month that needs more memory.

Argument errors (`ValueError`/`TypeError`) are raised at the call. Data errors fail the run instead: a missing column, settings that differ from the existing manifest, null or out-of-range coordinates, or unsafe partition values. Read them with `run.tail()` or `run.errors()`.

### `partition_by`: folders and jobs

| Form | Meaning |
|---|---|
| `"date"` or `["scenario", "date"]` | Folders come from those columns in the data. One job. |
| `{"month": ["2024-01", "2024-02"], "scenario": ["a", "b"]}` | One job per combination (product, in key order). Each job's values are bound on the source: `era5(month=...)`, the UDF's parameters, or a `parquet` hive folder (`{"state": ["TX"]}` reads `<path>/state=TX/`). Any iterable works, `range(1, 13)` too. Dates are sent as ISO text. |
| `[{"month": "2024-01"}, {"month": "2024-03"}]` | An explicit job list, all dicts with the same keys and one value per key. |

With jobs, the dict keys are the partition columns, and a `udf` source must return those columns with those values in every row. A job is named by its folder, such as `scenario=ssp245/month=2024-01`. All jobs launch together. Jobs over the team's batch quota wait as `pending` and start on their own.

### Re-running and `redo`

| You want | Do |
|---|---|
| Add a month | Run again with the new value in `partition_by`. Jobs already done are skipped, and the new folders merge into the output. |
| Run only some jobs | Pass only those values. |
| Redo a month | `redo=True` with just that value. It is read again from the source and rewritten. |
| Retry failures | `run.retry()` |
| Change `h3_res`, `file_res`, `fill`, `sort_by` or the partition columns | Write to a new `output`, or delete the old one. A run whose settings differ from the existing manifest fails and says so. |

With a single job (no dict in `partition_by`):

- With partition columns, a run creates the output or merges into it: each folder it writes replaces that folder, and other folders stay. `redo=True` does the same. A folder the source no longer produces is never deleted.
- Without partition columns, a run into an existing output fails, and `redo=True` replaces the whole output.
- `redo=True` on a single job refuses an output written one job per value. Don't run a single job into an output while per-job runs are writing to it.

A failed run never wipes a good dataset. A job that died midway is cleaned up and redone.

Deprecated, still accepted with a `FutureWarning`: `parts=` (use `partition_by`), `only=` (pass only those values), `force=` / `refresh=` (use `redo=True`), `append=` (a rerun merges anyway), `overwrite=` (new output path), and `row_group_size`, `compression`, `compression_level`, `key_columns`, `memory_budget`, `workers` as arguments (use `options`).

### Following a run

`partition` returns a `Run` (id starts with `grp:`):

| Call | Does |
|---|---|
| `run.tail()` | Prints each job's logs as `[job] …`, why a pending job is waiting, and a `n/total done, … running, … pending, … failed, … skipped` line whenever counts change, then failed jobs' errors. `run.wait()` is the silent version. Both take `timeout=` seconds. The run keeps going on the server if you stop waiting. |
| `run.status()` | `"failed"` if any job failed, else `"succeeded"` if all did, else `"running"` / `"pending"` |
| `run.jobs()`, `run.errors()` | job → status, and job → error for failed jobs |
| `run.succeeded()`, `run.failed()`, `run.skipped()`, `run.pending()` | job-id lists; `skipped` are jobs already done and left alone |
| `run.retry(jobs=None)` | Re-runs the failed jobs. One that failed while reading is read again; one that failed while partitioning reuses what was read. |
| `run.result()` | `{"output": ..., "parts": [job ids]}` once succeeded; raises if a job failed |
| `fused.h3.get_run(run_id)` | Gets the `Run` (or an index `TaskRun`) back in a new session |

`run.parts()` and `run.retry(parts=)` still work and warn.

While the partition job reads its input, it logs progress lines like:

```
[h3.partition] reading 120/800 files, 14.2 of 95.0 GiB on disk, 61.3 GiB decoded, 3 spills
```

A decoded size far above the instance's RAM means spilling; read fewer columns or use a bigger `engine`.

## Inspect a Parquet folder first

```python
report = fused.h3.inspect(path, *, point_column=None, columns=None, sample_files=3)
report   # prints a summary
```

It reads every file's footer and decodes `sample_files` files spread across the listing. It runs **locally** with your credentials (`fd://` resolves through your Fused login; `s3://` / `gs://` need local credentials). The `InspectReport` has:

| Field | Meaning |
|---|---|
| `files`, `bytes_on_disk` | file count and total size |
| `decoded_estimate`, `expansion` | estimated Arrow bytes once decoded, and decoded / on-disk ratio from the sample |
| `null_points` | with `point_column`: `{"columns": {col: null rows}, "unknown_files": n}` from footer stats (NaN not counted) |
| `schema_conflicts` | per column: `{"types": {type: file count}, "missing_in": [files], "resolvable": bool}`. `resolvable=False` needs `schema=`. |
| `bytes_by_column` | estimated decoded bytes per column |
| `suggested_columns` | every column except string/binary columns (not the point columns) that each take over 10% of decoded bytes |
| `suggested_call` | Python text for a `sources.parquet(...)` call, plus `on_null_point=` when there are null points |

## Examples

Points from Parquet:

```python
run = fused.h3.partition(
    fused.h3.sources.parquet("s3://bucket/raw/stations/"),
    "s3://bucket/hex/stations/",
    point_column=("lat", "lng"),
    h3_res=9, file_res=3,
)
run.tail()
```

A large multi-file Parquet folder:

```python
path = "s3://bucket/raw/ais/"
print(fused.h3.inspect(path, point_column=("lat", "lon")))   # sizes, nulls, schema, heavy columns

source = fused.h3.sources.parquet(
    path,
    columns=["mmsi", "ts", "lat", "lon", "sog"],   # drop heavy text columns
    filter=[("sog", ">", 0)],                      # skips row groups by footer stats
    read_threads=8,                                # many files on S3
)
run = fused.h3.partition(
    source, "s3://bucket/hex/ais/",
    point_column=("lat", "lon"),
    on_null_point="drop",                          # inspect found null coordinates
    h3_res=9, file_res=3,
    engine="large",                                # decoded size is well past "small"'s RAM
)
run.tail()
```

A year of ERA5, one job per month, filled to every res-7 cell:

```python
run = fused.h3.partition(
    fused.h3.sources.era5(outputs=["t2m_mean", "tp"]),
    "fd://me/era5_2024/",
    partition_by={"month": [f"2024-{m:02d}" for m in range(1, 13)]},
    point_column=("lat", "lng"), fill="nearest",
    h3_res=7, file_res=1,
    read_engine="large",       # a global month needs memory
)
run.tail()
if run.failed():
    run.retry().tail()
```

Hourly ERA5 takes `cadence="hourly"` and `partition_by={"date": [...]}` with `YYYY-MM-DD` values, so each day becomes a folder.

Data you build in Python, returned from a UDF, one job per scenario, with a value shared by every job:

```python
@fused.udf
def load(scenario: str, bucket: str):
    import pandas as pd
    df = pd.read_parquet(f"s3://{bucket}/raw/{scenario}.parquet")
    df["scenario"] = scenario          # each job's keys must be columns
    return df

fused.h3.partition(
    fused.h3.sources.udf(load, bucket="my-bucket"), "fd://me/scenarios/",
    partition_by={"scenario": ["ssp245", "ssp585"]},
    hex_column="h3_cell", h3_res=8,
).tail()
```

### `fill="nearest"` rules

- Each record batch must hold **one complete regular raster per key tuple**. Keys are `partition_by`, `key_columns`, and every non-float column (`date`, `hour`, …). Float columns are the values being filled.
- So int value columns get treated as keys: cast measurements to float.
- At least 2 distinct lats and 2 distinct lngs per batch; no NaN/inf coordinates. Longitudes in [0, 360) are fine.
- `sources.era5` yields exactly this shape. A `udf` source used with `fill` must return one complete raster per key tuple.

## Index

```python
run = fused.h3.index(
    path, hex_column="hex", time_column=None, *,
    partition_columns=None,   # defaults to the manifest's partition_by
    subset=None,              # {column: value(s)} folders to scope the run; "file" filters files
    redo=False,               # read files again (scoped with subset, else a full rebuild)
    engine="realtime",        # or "small", "large", ... for a big tree
    visibility=None,          # "team" (default for a new location) or "public" (Fused admins)
    options=None,             # {"workers": n, "instances": n}, below
) -> TaskRun
```

Starts a run that reads every file's row-group stats, and returns its `TaskRun` at once (a group `Run` when `instances` is above 1, see below). Follow it with `run.tail()`, or poll `run.status()` / `run.done()` / `run.error()`. A realtime run is limited to a few minutes and fails when it runs out of time. For a large tree, pass a batch `engine` such as `"large"`, or split the tree over several instances (see "Fanning out an index"). Engines never fall back from one to the other.

- A single `date` partition column is used as time automatically. Otherwise pass `time_column`: an in-file column, or a `key=value` folder holding `YYYY`, `YYYY-MM`, `YYYY-MM-DD` or an ISO instant.
- Re-running is incremental: unchanged folders are skipped, and a stopped or partly failed run resumes.
- `subset={"month": "2024-02"}` (values may be lists) indexes only those folders, so adding a partition to a large archive costs that partition. Keys must be the leading partition columns of the tree, in any order.
- `redo=True` with `subset` re-reads every file in those folders while the location keeps serving. Without `subset` it rebuilds the whole index, which is also how to change the location's columns.
- If some files fail, the rest are indexed and queryable. The run's error names the failed paths, and re-running retries them.
- Every file must share one H3 resolution. `/mount` paths can't be indexed; partition to `fd://` or `s3://` instead.
- The index belongs to your team, and only your team can re-index or delete it. `fused.h3.set_visibility(path, "public")` (Fused admins only) makes it readable by everyone; the files must be publicly readable on S3.

### Fanning out an index

`options={"instances": N}` runs the index as N concurrent slices of the folder tree, on any engine (`"realtime"` by default). `instances=1` is the default and changes nothing.

```python
run = fused.h3.index("s3://bucket/data/", options={"instances": 8})
run.tail()

# the same on batch instances, one job per slice
run = fused.h3.index("s3://bucket/data/", engine="small", options={"instances": 8})
run.tail()
```

The server lists the tree, skips folders whose fingerprint is unchanged, and balances the remaining leaf folders by bytes. A folder is never split, so you get fewer slices than N when fewer folders need work. `redo=True` and `subset=` apply as usual, and the slices cover only what they select.

With `instances` above 1 the call returns a group run (id starts with `grp:`), like `partition`, with one part per slice:

| Call | Does |
|---|---|
| `run.tail()` | Prints each slice's logs, then `slices finalized k/N` as slices finish |
| `run.failed()` | The failed slices |
| `run.retry()` | Re-runs only the failed slices, with the same folders |

The location is finalized once, when the last slice finishes, and stays `indexing` until then. A failed slice fails the location only after every slice has ended, and the error names that slice's folders. `run.retry()` then reruns it and the location becomes `ready`. `fused.h3.get_run(run_id)` gets the run back in a new session.

Batch slices queue against the team's job quota and start as capacity frees up. Realtime slices are not queued.

Use it for a large tree with many folders, where one run is slow or hits the realtime time limit. Don't use it when only a few folders changed, since there are then few slices and a single run is as fast. N has no cap and there is no back-pressure: every slice writes to the file-index database, so if it comes under pressure, put a pooler in front of it or lower N.

### Indexing a flat folder in batches

`subset={"file": ...}` is reserved for file names: a name, a glob on the name (`"1*.parquet"`, no `/`), or a list of them. On its own it applies to the whole tree, a flat folder included; it also combines with folder keys (`{"month": "2026-11", "file": ["a*.parquet"]}`). Files outside the filter are neither read nor dropped. A pattern that matches no file raises.

```python
for digit in "0123456789abcdef":
    fused.h3.index(
        "s3://bucket/flat/", subset={"file": f"{digit}*.parquet"}, engine="small",
    ).tail()
```

Progress is recorded per folder, not per file. The batch that leaves every file of a folder indexed records the folder, and only then does a later run skip it. Re-running a batch in a folder that was never fully recorded reads that batch again (for example after a realtime timeout), so pick batches that finish in one run, or use `engine="small"`.

`fused.h3.index_status(path)` returns `None` if the path was never indexed. Otherwise it returns a dict with `status` (`"queued"`, `"indexing"`, `"ready"` or `"failed"`), `indexing`, `job_id`, `files`, `resolution`, `hex_column`, `time_column`, `partition_columns` (name/type/distinct/min/max), `time_min`/`time_max`, `indexed_as_of`, `last_run_mode`, `last_run_finished_at` and `failures`.

Deprecated, still accepted with a `FutureWarning`: `prefix=` (use `subset=`), `overwrite=True` / `force=True` (use `redo=True`), `workers=` (use `options`).

## Query

```python
df = fused.h3.query(
    path,
    cell=None, *,                       # H3 string; matches the cell and its descendants
    lat=None, lng=None,                 # or a point
    bbox=None,                          # or (min_lng, min_lat, max_lng, max_lat)
    hex_range=None,                     # or (hex_min, hex_max) as H3 strings
    time_min=None, time_max=None,
    partition=None,                     # {"scenario": ["ssp245", "ssp585"], "date": "2050-01"}
    partition_range=None,               # {"date": ("2050-01", None)}
    columns=None,
    max_row_groups=None,                # page size, not a result limit
)
```

- **Only runs inside a UDF on a Fused realtime or batch instance.** Called from a notebook or script it raises `RuntimeError`. Wrap it in a `@fused.udf` and `fused.run` that, or call `/h3/query` over HTTP (see [`map.md`](map.md)).
- Reads your team's index of `path`, else the public one. The server returns a read plan and the rows are read in the calling process.
- Give at most one spatial selector; none returns everything. A bbox keeps rows whose cell centre is inside, so the edge is accurate to one cell.
- Date partitions match by overlap (`"2050-01"` matches every day in that month). A `partition_range` on the time column also narrows the time window.
- Only space, time and partition values are filtered. Filter other columns on the returned DataFrame.
- There is no row cap, so **the whole result is held in memory**, and a result too big for the instance fails the job. Split the area or time window into narrower queries (fan out with `fused.submit`). Row order is not defined.

| Error | Meaning |
|---|---|
| 404 | path was never indexed |
| 409 | index not ready yet (poll `index_status`), a data file changed since indexing (re-run `index`), or re-indexed mid-query (run it again) |
| 400 | two selectors, `lat` without `lng`, time bounds on a timeless location, or a `partition`/`partition_range` naming a non-partition column or an ill-typed value |

Other management calls: `fused.h3.indexed_files(path, *, prefix=None)` (iterator of indexed file paths) and `fused.h3.delete_index(path, *, prefix=None)`. These two still take `prefix=` (a folder under `path`, or a list for `delete_index`), not `subset=`. With `prefix`, `delete_index` drops only the index under those folders. The data files are never touched.

## Older APIs

These are still exported but write a different layout (no `_manifest.json`, extra `_sample`/`_overview` files). Build new datasets with `partition`; reach for these only when maintaining a dataset built with them:

- `fused.h3.run_ingest_raster_to_h3(input_path, output_path, metrics="cnt", res=None, ...)`: GeoTIFF → hex with `_sample` and `_overview/` files, run as distributed jobs.
- `fused.h3.run_partition_to_h3(...)`: re-partitions data that already has a `hex` column, in the same layout.
- `fused.h3.read_hex_table(dataset_path, hex_ranges_list, ...)` and `persist_hex_table_metadata` / `read_hex_table_with_persisted_metadata`: range reads over those datasets.

docs.fused.io's H3 pages ("Converting to H3", `fused.h3` reference) describe only these older APIs.
