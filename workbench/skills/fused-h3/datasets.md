# Published hex datasets: ERA5 and GridMET

Fused publishes two weather datasets already partitioned to H3 resolution 7, on Source Cooperative's public bucket. Read them directly, or through the Fused API's `/retrieve` routes. No ingestion and no credentials needed.

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
- `format`: `csv` (default), `json`, `parquet` or `index`.
- `limit`: point routes default 5,000, max 10,000; bbox and hex-range routes default 50,000, max 100,000.

In CSV and JSON responses, `hex` is an H3 string.

```python
import pandas as pd
url = ("https://www.fused.io/server/v1/retrieve/era5/daily/point"
       "?lat=40.0&lng=-105.27&date_min=2020-07-01&date_max=2020-07-31&variables=t2m_max,tp")
df = pd.read_csv(url)
```

The bbox cover is approximate at res 7. Use the REST routes for a point or small area over a date range. For larger pulls, read the Parquet directly.

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
