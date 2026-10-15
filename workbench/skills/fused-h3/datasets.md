# Published hex datasets: ERA5 and GridMET

Fused publishes two weather datasets already partitioned to H3 resolution 7, on Source Cooperative's public bucket. Read the daily ones with `fused.h3.query`, any of them through the Fused API's `/retrieve` routes, or as Parquet directly. No ingestion and no credentials needed.

| Dataset | Path | Layout | Columns |
|---|---|---|---|
| ERA5 daily (global, 1940→) | `s3://us-west-2.opendata.source.coop/fused/era5-hex/era5_daily/` | `month=YYYY-MM/<res-1 cell>.parquet` | `hex`, `date`, `t2m_min`, `t2m_max`, `t2m_mean`, `d2m`, `sp`, `tp`, `sf`, `sde`, `ssrd`, `pev`, `e`, `u10`, `v10`, `skt`, `swvl1-4`, `stl1-4` |
| ERA5 hourly | `s3://us-west-2.opendata.source.coop/fused/era5-hex/era5_hourly/` | `month=YYYY-MM/day=YYYY-MM-DD/<res-1 cell>.parquet` | `hex`, `date`, `hour`, `t2m` plus the daily variables above except the `t2m_*` trio |
| GridMET daily (CONUS, 1979→) | `s3://us-west-2.opendata.source.coop/fused/gridmet-hex/gridmet_daily/` | `month=YYYY-MM/<res-1 cell>.parquet` | `hex`, `date`, `pr`, `rmax`, `rmin`, `sph`, `srad`, `tmmn`, `tmmx` |

`hex` is uint64 at resolution 7; values are float32. Units, daily reductions and processing notes are in each dataset's README (`.../era5-hex/README.md`, `.../gridmet-hex/README.md`). Read it before interpreting a variable: temperatures are Kelvin, and ERA5 accumulations use a 01:00→00:00 window.

## REST: `/retrieve` routes (point, bbox, cell range)

Base: `https://www.fused.io/server/v1/retrieve/`. Public, no token.

| Route | Selector params |
|---|---|
| `era5/daily/point`, `era5/hourly/point`, `gridmet/point` | `lat` + `lng`, or `cell` (res-7 H3 string) |
| `era5/daily/bbox`, `era5/hourly/bbox`, `gridmet/bbox` | `min_lng`, `min_lat`, `max_lng`, `max_lat` |
| `era5/daily/hex-range`, `era5/hourly/hex-range`, `gridmet/hex-range` | `hex_min`, `hex_max` (H3 strings) |

Every route also requires `date_min` and `date_max` (inclusive) and takes these optional params:
- `variables=t2m_max,tp`: comma-separated; key columns are always returned.
- `format`: `csv` (default), `json` or `parquet` return rows. `index` returns the matching row groups' metadata, for callers that read the files themselves. `stats` returns per-row-group min/max/null_count for `variables`, plus each row group's H3 range and partition: a small response for a coarse overview (newer servers only; older ones answer 422).
- `limit`: point routes default 5,000, max 10,000; bbox and hex-range routes default 50,000, max 100,000.
- `max_row_groups`: default 128, max 256. A query matching more rows than `limit` or more row groups than `max_row_groups` is rejected, not truncated. Narrow the dates or area.

Every response carries an `ETag`. Send it back as `If-None-Match` to get `304 Not Modified` when nothing changed.

In CSV and JSON responses, `hex` is an H3 string.

```python
import pandas as pd
url = ("https://www.fused.io/server/v1/retrieve/era5/daily/point"
       "?lat=40.0&lng=-105.27&date_min=2020-07-01&date_max=2020-07-31&variables=t2m_max,tp")
df = pd.read_csv(url)
```

The bbox cover is approximate at res 7. Use the REST routes for a point or small area over a date range. For larger pulls, use `fused.h3.query` or read the Parquet directly.

## `fused.h3.query`

ERA5 daily and GridMET daily are public H3 locations (time column `date`), so `fused.h3.query` reads them with no indexing step and no sign-in, and has no row cap. Pass the root **without a trailing slash**; with one, the query 404s. ERA5 hourly is not indexed: use its `/retrieve` routes or read its Parquet.

```python
df = fused.h3.query(
    "s3://us-west-2.opendata.source.coop/fused/era5-hex/era5_daily",
    lat=40.0, lng=-105.27,
    time_min="2020-07-01", time_max="2020-07-31",
    columns=["hex", "date", "t2m_max", "tp"],
)
```

## Direct Parquet read

Files are keyed by the res-1 parent cell, so compute it and read one file per month:

```python
import h3, pyarrow.parquet as pq, pyarrow.fs as pafs

cell = h3.latlng_to_cell(40.0, -105.27, 7)
parent = h3.cell_to_parent(cell, 1)
s3 = pafs.S3FileSystem(anonymous=True, region="us-west-2")
table = pq.read_table(
    f"us-west-2.opendata.source.coop/fused/era5-hex/era5_daily/month=2020-07/{parent}.parquet",
    filesystem=s3,
    filters=[("hex", "=", h3.str_to_int(cell))],
    columns=["hex", "date", "t2m_max", "tp"],
)
```

Files are sorted by `hex` with row-group statistics, so the filter skips most of each file.

## Building your own

To produce the same kind of dataset for another gridded source, see `fused.h3.sources.era5` and `fill="nearest"` in the main skill.
