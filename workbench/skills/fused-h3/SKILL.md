---
name: fused-h3
description: Ingest data into H3 hex datasets and query them with the `fused.h3` API — partitioning points, geometries, gridded rasters (ERA5-style) or tables that already carry an H3 column into hex-sorted Parquet, registering them with `fused.h3.index`, and reading them back with `fused.h3.query`. Also covers the published ERA5 and GridMET hex datasets. Use when converting data to H3, building or appending to a hex dataset, querying one by point/bbox/cell/time, or reading ERA5/GridMET weather by location.
---

# H3 ingestion with `fused.h3`

`fused.h3` turns tabular data into a **hex dataset**: Parquet files sorted by a uint64 `hex` column, one file per coarse parent cell, described by a `_manifest.json`. Once **indexed**, the dataset is queryable by point, bbox, cell, time and partition values without scanning every file.

The workflow is always:

1. **Source**: get the data as Arrow record batches (`fused.h3.sources.*`, or a DataFrame).
2. **Partition**: `fused.h3.partition(...)` writes the hex dataset.
3. **Index**: `fused.h3.index(path, ...)` registers it with Fused.
4. **Query**: `fused.h3.query(path, ...)` returns a DataFrame.

Steps 1–2 must run **inside a Fused UDF** (they rely on libraries that ship only in the runtime; a local `fused` install raises `ImportError`). Steps 3–4 work from anywhere the `fused` SDK is authenticated.

For the published ERA5 and GridMET hex datasets (read-only, no ingestion needed), see [`datasets.md`](datasets.md).

## Choosing how rows get a hex

`partition` needs exactly one of `hex_column=` or `point_column=`:

| Your data | Call |
|---|---|
| Already has an **integer** H3 column | `hex_column="h3"`, with `h3_res` set to that column's resolution. It is cast to uint64 and **renamed to `hex`** in the output. Convert string ids first: `df["h3"] = df["h3"].map(h3.str_to_int)`. |
| lat/lng columns | `point_column=("lat", "lng")`, lat first |
| A WKB geometry column (GeoDataFrame) | `point_column="geometry"`. Points hex themselves; other shapes get the cell of their planar centroid. One row in, one row out: polygons are **not** polyfilled. |
| A regular lat/lng raster (grid of values, e.g. 0.25° climate data) that should cover **every** cell | `point_column=("lat", "lng"), fill="nearest"`. Each cell at `h3_res` takes the nearest raster point's values. |

Coordinates must be EPSG:4326 degrees; reproject first. Geometries crossing the antimeridian or wrapping a pole get a wrong planar centroid: split them, or pass lat/lng.

## Partition

```python
fused.h3.partition(
    data,                      # record-batch iterator, DataFrame, GeoDataFrame, pa.Table or RecordBatch
    output,                    # "s3://bucket/prefix/", "fd://...", or a local path
    *,
    hex_column=None, point_column=None,
    h3_res=7,                  # resolution of the `hex` column (one row per cell per key)
    file_res=1,                # parent resolution that groups rows into files
    fill=None,                 # None | "nearest"
    partition_by=None,         # column(s) that become key=value folders, e.g. "date" or ["scenario", "date"]
    sort_by=None,              # secondary sort inside each file, after `hex`
    overwrite=False, append=False,
    row_group_size=65_536, compression="zstd", compression_level=5,
    key_columns=None,          # dictionary-encoded columns; defaults to partition_by
) -> None
```

**Output layout:** `<output>/<col>=<value>/.../<file_res parent cell>.parquet` plus `<output>/_manifest.json`. Each file holds `hex` (uint64) and every input column, sorted by `hex` then `sort_by`. Point and geometry columns are kept.

**Resolutions:** `0 <= file_res <= h3_res <= 15`. `file_res=1` (842 global parents) is what the ERA5/GridMET datasets use at res 7. For finer `h3_res` or regional data, raise `file_res` so each file holds a manageable number of rows.

**`partition_by` values** become folder names: dates as `YYYY-MM-DD`, timestamps as ISO, ints as digits. Values must be non-null, non-empty, not start with `_`, and contain no `/`.

**Re-running:** an existing output (or leftovers from an aborted run) fails unless you pass `overwrite=True`. To add new partitions (a new day, a new scenario) without rewriting the rest, pass `append=True`. Append needs `partition_by` and requires `h3_res`, `file_res`, `fill`, `partition_by`, `sort_by` and partition types to match the manifest. Each leaf folder it writes replaces that folder, so re-appending a day is idempotent.

### `fill="nearest"` rules

- Each record batch must hold **one complete regular raster per key tuple**. Keys are `partition_by`, `key_columns`, and every non-float column (`date`, `hour`, …). Float columns are the values being filled.
- So int value columns get treated as keys: cast measurements to float.
- At least 2 distinct lats and 2 distinct lngs per batch; no NaN/inf coordinates. Longitudes in [0, 360) are fine.

## Sources

Any `Iterator[pa.RecordBatch]` works as `data`. Prefer a generator for data larger than memory.

| Source | Use |
|---|---|
| `fused.h3.sources.parquet(path, *, columns=None, batch_size=65_536)` | One Parquet file or every `.parquet` under a folder (recursive, sorted). Local, `s3://`, `gs://`, `az://`, `fd://`. `partition` rejects bare paths; wrap them with this. |
| `fused.h3.sources.table(data)` | DataFrame / GeoDataFrame / Arrow table. Geometry becomes WKB; a named index is kept as a column. Passing the DataFrame straight to `partition` does the same. |
| `fused.h3.sources.era5(year, month, *, outputs, cadence="daily", days=None, bbox=None, read_workers=16)` | ERA5 from Google's public ARCO Zarr as `lat, lng, date[, hour], <outputs…>` batches, ready for `fill="nearest"`. Daily outputs include `t2m_min/max/mean`, `tp`, `d2m`, `sp`, `u10`, `v10`, `ssrd`, soil layers; hourly uses `t2m`. `bbox=(min_lng, min_lat, max_lng, max_lat)` trims memory and output but not download. |

xarray isn't accepted directly: convert to a DataFrame of `lat, lng, <keys>, <values>` per time step, or write a generator shaped like `sources.era5`.

## Examples

Points from Parquet:

```python
@fused.udf(cache_max_age=0)
def udf(src: str = "s3://bucket/raw/stations/", out: str = "s3://bucket/hex/stations/"):
    fused.h3.partition(
        fused.h3.sources.parquet(src),
        out,
        point_column=("lat", "lng"),
        h3_res=9, file_res=3,
        overwrite=True,
    )
```

A gridded climate month, filled to every res-7 cell, one folder per day:

```python
@fused.udf(cache_max_age=0)
def udf(year: int = 2024, month: int = 1, out: str = "s3://bucket/era5_daily_hex/"):
    batches = fused.h3.sources.era5(year, month, outputs=["t2m_mean", "tp"])
    fused.h3.partition(
        batches, out,
        point_column=("lat", "lng"), fill="nearest",
        h3_res=7, file_res=1, partition_by="date",
        append=True,   # first run: overwrite=True instead
    )
```

A table that already has H3 ids, split by scenario:

```python
fused.h3.partition(df, out, hex_column="h3_cell", partition_by=["scenario", "year"], h3_res=8)
```

Long ingests (many months, global fills) exceed the realtime timeout: run them with `engine="large"`. **Run appends one at a time.** `append=True` rewrites `_manifest.json` by read-merge-write with no lock, so parallel `udf.map()` workers appending to the same output silently drop each other's manifest entries. Loop over months sequentially inside one batch job, or give each worker its own `output`.

## Index and query

```python
fused.h3.index(
    path, hex_column="hex", time_column=None, *,
    partition_columns=None,   # defaults to the manifest's partition_by
    instance_type="small", wait=True, overwrite=False,
) -> dict
```

Runs a batch job that reads every file's row-group stats. A single `date` partition column is used as time automatically. Otherwise pass `time_column` (an in-file column or a `key=value` folder holding `YYYY`, `YYYY-MM`, `YYYY-MM-DD` or an ISO instant). Re-running is incremental. Every file must share one H3 resolution.

Inside a realtime UDF, `wait=True` gives up after ~90 s with `TimeoutError` while the job keeps going. Poll `fused.h3.index_status(path)` until `status == "ready"`.

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
    columns=None, format="parquet", max_row_groups=None,
)
```

Give at most one spatial selector; none returns everything. Date partitions match by overlap (`"2050-01"` matches every day in that month). Results are capped at 10,000 rows. Narrow the query rather than paging.

| Error | Meaning |
|---|---|
| 404 | path was never indexed |
| 409 | index still building: poll `index_status` |
| 400 | two selectors, `lat` without `lng`, or time bounds on a dataset with no time |
| 413 | too many row groups: narrow the query or raise `max_row_groups` (≤ 4096) |

Other management calls: `fused.h3.index_status(path)`, `fused.h3.indexed_files(path, prefix=None)`, and `fused.h3.delete_index(path)` (drops the index, keeps the files).

## Older APIs

These are still exported but write a different layout (no `_manifest.json`, extra `_sample`/`_overview` files). Build new datasets with `partition`; reach for these only when maintaining a dataset built with them:

- `fused.h3.run_ingest_raster_to_h3(input_path, output_path, metrics="cnt", res=None, ...)`: GeoTIFF → hex with `_sample` and `_overview/` files, run as distributed jobs.
- `fused.h3.run_partition_to_h3(...)`: re-partitions data that already has a `hex` column, in the same layout.
- `fused.h3.read_hex_table(dataset_path, hex_ranges_list, ...)` and `persist_hex_table_metadata` / `read_hex_table_with_persisted_metadata`: range reads over those datasets.

docs.fused.io's H3 pages ("Converting to H3", `fused.h3` reference) describe only these older APIs.
