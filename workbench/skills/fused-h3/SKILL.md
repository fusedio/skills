---
name: fused-h3
description: Ingest data into H3 hex datasets and query them with the `fused.h3` API — partitioning points, geometries, gridded rasters (ERA5-style) or tables that already carry an H3 column into hex-sorted Parquet as server-side runs, registering them with `fused.h3.index`, and reading them back with `fused.h3.query`. Also covers the published ERA5 and GridMET hex datasets. Use when converting data to H3, building or appending to a hex dataset, following or retrying a partition/index run, querying one by point/bbox/cell/time, or reading ERA5/GridMET weather by location.
---

# H3 ingestion with `fused.h3`

`fused.h3` turns tabular data into a **hex dataset**: Parquet files sorted by a uint64 `hex` column, one file per coarse parent cell, described by a `_manifest.json`. Once **indexed**, the dataset is queryable by point, bbox, cell, time and partition values without scanning every file.

The workflow is always:

1. **Source**: describe the input with `fused.h3.sources.parquet`, `.era5` or `.udf` (or pass a cloud Parquet path).
2. **Partition**: `fused.h3.partition(...)` starts a server-side run that writes the hex dataset and returns a `Run`.
3. **Index**: `fused.h3.index(path, ...)` starts a server-side run that registers it and returns a `TaskRun`.
4. **Query**: `fused.h3.query(path, ...)` returns a DataFrame.

All four steps work from anywhere the `fused` SDK is authenticated: a notebook, a script, or a UDF. Nothing is read or uploaded from the calling machine. `partition` and `index` send a description of the work to the Fused server and **return as soon as the run has started**. Call `run.tail()` to follow it to the end.

For the published ERA5 and GridMET hex datasets (read-only, no ingestion needed), see [`datasets.md`](datasets.md).

## Choosing how rows get a hex

`partition` needs exactly one of `hex_column=` or `point_column=`:

| Your data | Call |
|---|---|
| Already has an **integer** H3 column | `hex_column="h3"`, with `h3_res` set to that column's resolution. It is cast to uint64 and **renamed to `hex`** in the output. Convert string ids first: `df["h3"] = df["h3"].map(h3.str_to_int)`. |
| lat/lng columns | `point_column=("lat", "lng")`, lat first |
| A WKB geometry column (GeoDataFrame) | `point_column="geometry"`. Points hex themselves; other shapes get the cell of their planar centroid. One row in, one row out: polygons are **not** polyfilled. Null or empty geometries fail the run. |
| A regular lat/lng raster (grid of values, e.g. 0.25° climate data) that should cover **every** cell | `point_column=("lat", "lng"), fill="nearest"`. Each cell at `h3_res` takes the nearest raster point's values. |

Coordinates must be EPSG:4326 degrees. Nothing is reprojected, and projected values (UTM metres, say) fail the run. Geometries crossing the antimeridian or wrapping a pole get a wrong planar centroid: split them, or pass lat/lng.

## Sources

`data` must be a `fused.h3.sources` source, or a `s3://` / `gs://` / `gcs://` / `fd://` path, which means `sources.parquet(path)`. A DataFrame, Arrow table, record-batch iterator, xarray dataset, local path, `memory://` or `az://` path raises `TypeError`. To partition data you hold in Python, return it from a UDF and pass `sources.udf(...)`.

| Source | Use |
|---|---|
| `fused.h3.sources.parquet(path, *, columns=None, batch_size=65_536, **hive_keys)` | One Parquet file or every `.parquet` under a folder (recursive, sorted). Hive keys pick a subfolder: `year=2020` reads `<path>/year=2020/` and adds `year` as a string column when the files lack it. |
| `fused.h3.sources.era5(*, outputs, month=None, date=None, cadence="daily", bbox=None, read_workers=16)` | ERA5 from Google's public ARCO Zarr as `lat, lng, month, date[, hour], <outputs…>` batches, ready for `fill="nearest"`. Give exactly one of `month="YYYY-MM"` or `date="YYYY-MM-DD"`, here or per part. Daily outputs include `t2m_min/max/mean`, `tp`, `d2m`, `sp`, `u10`, `v10`, `ssrd`, soil layers; hourly uses `t2m`. `bbox=(min_lng, min_lat, max_lng, max_lat)` trims memory and output but not download. |
| `fused.h3.sources.udf(my_udf)` | Runs a `@fused.udf` on the server, once per part. Its parameters are the source's inputs, and it must **return** a DataFrame, GeoDataFrame, Arrow `Table` or `RecordBatch`, not a generator. The UDF is serialized, so import inside its body and don't rely on local files or variables. GeoDataFrame geometry arrives as WKB. |

`udf` and `era5` sources are first read by an `h3.read` batch job per part on `read_engine` (default `"small"`). That job caches the rows under `<output>/.fused-h3-source/`, and the partition job starts once the read succeeds. A re-run reuses the cache for an unchanged part (same source, inputs and UDF code). Pass `refresh=True` to read again.

## Partition

```python
run = fused.h3.partition(
    data,                      # a fused.h3.sources source, or an s3:// / gs:// / fd:// Parquet path
    output,                    # "fd://...", "s3://bucket/prefix/" or "gs://..."; not local, not az://
    *,
    hex_column=None, point_column=None,
    h3_res=7,                  # resolution of the `hex` column (one row per cell per key)
    file_res=1,                # parent resolution that groups rows into files
    fill=None,                 # None | "nearest"
    partition_by=None,         # column(s) that become key=value folders, e.g. "date" or ["scenario", "date"]
    sort_by=None,              # secondary sort inside each file, after `hex`
    overwrite=False, append=False,
    parts=None,                # one dict of inputs per part: [{"month": "2024-01"}, ...]
    only=None, force=False,    # run a subset of parts / redo parts already marked done
    refresh=False,             # re-read a cached udf/era5 part
    read_engine="small",       # batch instance for udf/era5 read jobs
    engine="small",            # partition job: batch instance, or "realtime" (parquet sources only)
    row_group_size=65_536, compression="zstd", compression_level=5,
    key_columns=None,          # dictionary-encoded columns; defaults to partition_by
    memory_budget=2 << 30,     # bytes of buffered rows before spilling inside output
    workers=None,              # file-writer threads; default 32 for object storage
) -> fused.h3.Run
```

**Output layout:** `<output>/<col>=<value>/.../<file_res parent cell>.parquet` plus `<output>/_manifest.json`. Each file holds `hex` (uint64) and every input column, sorted by `hex` then `sort_by`. Point and geometry columns are kept.

**Resolutions:** `0 <= file_res <= h3_res <= 15`. `file_res=1` (842 global parents) is what the ERA5/GridMET datasets use at res 7. For finer `h3_res` or regional data, raise `file_res` so each file holds a manageable number of rows.

**`partition_by` values** become folder names: dates as `YYYY-MM-DD`, timestamps as ISO, ints as digits. Values must be non-null, non-empty, not start with `_`, and contain no `/`.

**Engines:** the partition job runs as a `"small"` batch job by default, with no time limit. Pass `"medium"`, `"large"`, … for a bigger instance. `engine="realtime"` is limited to a few minutes and only suits small Parquet inputs: a `udf` or `era5` source raises with it. `read_engine` must be a batch instance; raise it for a UDF or ERA5 month that needs more memory.

**Re-running:** an existing output (or leftovers from an aborted run) fails unless you pass `overwrite=True`. To add new partitions (a new day, a new scenario) without rewriting the rest, pass `append=True`. Append needs `partition_by` and requires `h3_res`, `file_res`, `fill`, `partition_by`, `sort_by` and partition types to match the manifest. Each leaf folder it writes replaces that folder, so re-appending a day is idempotent. A failed run never wipes a good dataset.

Argument errors (`ValueError`/`TypeError`) are raised at the call. Data errors fail the run instead: a missing column, an existing output without `overwrite`/`append`, a manifest mismatch, null or out-of-range coordinates, or unsafe partition values. Read them with `run.tail()` or `run.errors()`.

### Parts: many jobs in one call

`parts=` splits the work into one read job and one partition job per dict, all launched together. Each dict binds the source's inputs: `{"month": "2024-01"}` for `era5`, the UDF's parameters for `udf`, or hive keys for `parquet` (`{"state": "TX"}` reads `<path>/state=TX/`).

- Every dict has the same keys, and those keys become the partition columns. Leave `partition_by` unset, or set it to exactly those keys. For a `udf` source, the UDF must return those columns with those values.
- `append` is implied and `overwrite` is refused. Delete the output first, or pass `force=True` to redo parts.
- A finished part writes `_parts/<part id>.json` and is skipped on a re-run unless you pass `force=True`. The part id is its inputs joined as `k=v-k=v` (e.g. `month=2024-01`). A part that died midway is cleaned up and redone.
- `only=["month=2024-03"]` runs a subset. Jobs over the team's batch quota wait as `pending` and start on their own.

Prefer `parts=` over looping `append=True` calls. Separate concurrent appends to *different* leaf folders are safe on S3 and local storage (other backends warn). Two runs writing the *same* folder race on its files.

### Following a run

`partition` returns a `Run` (id starts with `grp:`):

| Call | Does |
|---|---|
| `run.tail()` | Prints each part's logs as `[part] …` plus progress counts until every part finishes, then failed parts' errors. `run.wait()` is the silent version. Both take `timeout=` seconds. The run keeps going on the server if you stop waiting. |
| `run.status()` | `"failed"` if any part failed, else `"succeeded"` if all did, else `"running"` / `"pending"` |
| `run.parts()`, `run.errors()` | part → status, and part → error for failed parts |
| `run.succeeded()`, `run.failed()`, `run.skipped()`, `run.pending()` | part-name lists |
| `run.retry(parts=None)` | Re-runs the failed parts (re-reads only parts that failed while reading) |
| `run.result()` | `{"output": ..., "parts": [...]}` once succeeded; raises if a part failed |
| `fused.h3.get_run(run_id)` | Gets the `Run` (or an index `TaskRun`) back in a new session |

## Examples

Points from Parquet:

```python
run = fused.h3.partition(
    fused.h3.sources.parquet("s3://bucket/raw/stations/"),
    "s3://bucket/hex/stations/",
    point_column=("lat", "lng"),
    h3_res=9, file_res=3,
    overwrite=True,
)
run.tail()
```

A year of ERA5, one part per month, filled to every res-7 cell:

```python
run = fused.h3.partition(
    fused.h3.sources.era5(outputs=["t2m_mean", "tp"]),
    "fd://me/era5_2024/",
    parts=[{"month": f"2024-{m:02d}"} for m in range(1, 13)],
    point_column=("lat", "lng"), fill="nearest",
    h3_res=7, file_res=1,
    read_engine="large",       # a global month needs memory
)
run.tail()
if run.failed():
    run.retry().tail()
```

Hourly ERA5 takes `cadence="hourly"` and a `{"date": "YYYY-MM-DD"}` per part, so each day becomes a folder.

Data you build in Python, returned from a UDF, one part per scenario:

```python
@fused.udf
def load(scenario: str):
    import pandas as pd
    df = pd.read_parquet(f"s3://bucket/raw/{scenario}.parquet")
    df["scenario"] = scenario          # each part's keys must be columns
    return df

fused.h3.partition(
    fused.h3.sources.udf(load), "fd://me/scenarios/",
    parts=[{"scenario": s} for s in ["ssp245", "ssp585"]],
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
    engine="realtime",        # or "small", "large", ... for a big tree
    overwrite=False,
    prefix=None,              # folder(s) under path to scope the run, e.g. "month=2024-02"
    force=False,              # re-read unchanged folders within the scope
    workers=None,             # files read at once; default 32
    visibility=None,          # "team" (default for a new location) or "public" (Fused admins)
) -> TaskRun
```

Starts a run that reads every file's row-group stats, and returns its `TaskRun` at once. Follow it with `run.tail()`, or poll `run.status()` / `run.done()` / `run.error()`. A realtime run is limited to a few minutes and fails when it runs out of time. For a large tree, pass a batch `engine` such as `"large"`. Engines never fall back from one to the other.

- A single `date` partition column is used as time automatically. Otherwise pass `time_column`: an in-file column, or a `key=value` folder holding `YYYY`, `YYYY-MM`, `YYYY-MM-DD` or an ISO instant.
- Re-running is incremental: unchanged folders are skipped, and a stopped or partly failed run resumes. `overwrite=True` rebuilds from scratch, and is required to change the location's columns.
- `prefix="date=2024-02"` (or a list of folders) indexes only those folders. That makes adding a partition to a large archive cheap. It cannot be combined with `overwrite`. `force=True` re-reads the scoped folders even if unchanged, while the location keeps serving.
- If some files fail, the rest are indexed and queryable. The run's error names the failed paths, and re-running retries them.
- Every file must share one H3 resolution.
- The index belongs to your team, and only your team can re-index or delete it. `fused.h3.set_visibility(path, "public")` (Fused admins only) makes it readable by everyone.

`fused.h3.index_status(path)` returns `None` if the path was never indexed. Otherwise it returns a dict with `status` (`"queued"`, `"indexing"`, `"ready"` or `"failed"`), `indexing`, `job_id`, `files`, `resolution`, `time_column`, `partition_columns` (name/type/distinct/min/max), `time_min`/`time_max`, `indexed_as_of` and `failures`.

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
    engine="auto",                      # "auto" | "server" | "client"
)
```

- Reads your team's index of `path`, else the public one. Public locations can be queried without signing in.
- Give at most one spatial selector; none returns everything. A bbox keeps rows whose cell centre is inside, so the edge is accurate to one cell.
- Date partitions match by overlap (`"2050-01"` matches every day in that month).
- Only space, time and partition values are filtered. Filter other columns on the returned DataFrame.
- There is no row cap and no 413. The server returns a large result a page at a time, and `query` follows every page and concatenates them, so **the whole result is held in memory**. For big pulls, split the area or time window into narrower queries (fan out with `fused.submit`). Row order is not defined.
- `engine="auto"` reads public locations directly in this process when it can, and otherwise uses the server. Both return the same rows.

| Error | Meaning |
|---|---|
| 404 | path was never indexed |
| 409 | index not ready yet (poll `index_status`), a data file changed since indexing (re-run `index`), or re-indexed mid-query (run it again) |
| 400 | two selectors, `lat` without `lng`, time bounds on a timeless location, or a `partition`/`partition_range` naming a non-partition column or an ill-typed value |

Other management calls: `fused.h3.indexed_files(path, prefix=None)` (iterator of file paths) and `fused.h3.delete_index(path, prefix=None)`. With `prefix`, `delete_index` drops only the index under those folders. The data files are never touched.

## Older APIs

These are still exported but write a different layout (no `_manifest.json`, extra `_sample`/`_overview` files). Build new datasets with `partition`; reach for these only when maintaining a dataset built with them:

- `fused.h3.run_ingest_raster_to_h3(input_path, output_path, metrics="cnt", res=None, ...)`: GeoTIFF → hex with `_sample` and `_overview/` files, run as distributed jobs.
- `fused.h3.run_partition_to_h3(...)`: re-partitions data that already has a `hex` column, in the same layout.
- `fused.h3.read_hex_table(dataset_path, hex_ranges_list, ...)` and `persist_hex_table_metadata` / `read_hex_table_with_persisted_metadata`: range reads over those datasets.

docs.fused.io's H3 pages ("Converting to H3", `fused.h3` reference) describe only these older APIs.
