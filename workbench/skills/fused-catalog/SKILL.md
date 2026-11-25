---
name: fused-catalog
description: Read satellite and raster collections in a UDF with `fused.catalog`. `fused.catalog.list()` lists the collections (Harmonized Landsat Sentinel-2 `hls2-s30` and `hls2-l30`, elevation, land cover and more) with their bands and date ranges; `fused.catalog.imagery()` reads one over a bbox or geometry and dates as H3 cells (`output="hex"`), pixel chips (`output="chip"`) or zonal statistics per polygon (`output="stats"`), with cloud masking and day, weekly, monthly or yearly composites. Use when a UDF needs Sentinel-2 or Landsat reflectance, NDVI or another band index, a cloud-free composite, a per-field time series, or when code mentions `fused.catalog`.
---

# Reading imagery with `fused.catalog`

`fused.catalog.imagery` returns a DataFrame for a collection, area and dates: no STAC search, no COG reads. Call it inside a UDF. `help(fused.catalog.imagery)` is the full reference.

## Collections

```python
fused.catalog.list()   # one row per collection: name, bands, time_min, time_max, has_cloud_mask
```

- `hls2-s30` (Sentinel-2) and `hls2-l30` (Landsat): 30 m, bands such as `red`, `green`, `blue`, `nir`, `swir1`, `swir2` as int16 reflectance scaled by 10,000 (-9999 no data), plus the `fmask` cloud mask.
- Always pass `bands=`: the default is every band but `fmask`.
- Elevation, land cover and other rasters read the same way: `fused.catalog.imagery("cop-dem-glo-30", bounds)` returns `hex`, `data`.

## Pick an output

| `output=` | One row per | Use for |
|---|---|---|
| `"hex"` (default) | H3 cell and scene | maps, joins and aggregation on H3 |
| `"chip"` | scene and tile | pixel arrays (numpy) |
| `"stats"` | polygon, with a list per date | per-field time series |

## H3 cells

```python
@fused.udf
def udf(bounds: fused.types.Bounds = [-95.32, 40.68, -95.30, 40.70]):
    return fused.catalog.imagery(
        "hls2-s30", bounds, time="2025-06", bands=["red", "nir"],
        mask_clouds=True, max_cloud_pct=20,
    )
```

Columns `hex`, `red`, `nir`, `datetime`, `cloud_pct`; about 100k rows for this 2 km box and month.

- Each cell takes the pixel under its centre, not an average. `h3_res` defaults to the pixel size (12 for 30 m); a coarser `h3_res=10` samples, so aggregate finer cells to average.
- A cell where two tiles overlap gets a row per scene. `composite="day"` gives one row per cell and day.
- `sql="select datetime, avg(nir) nir from df group by 1"` runs DuckDB over the result (table `df`) before it is returned.

Monthly median NDVI:

```python
@fused.udf
def udf(bounds: fused.types.Bounds = [-95.32, 40.68, -95.30, 40.70]):
    df = fused.catalog.imagery(
        "hls2-s30", bounds, time="2025-04/2025-09", bands=["red", "nir"],
        mask_clouds=True, composite="month", reducer="median",
    )
    df["ndvi"] = (df.nir - df.red) / (df.nir + df.red)
    return df
```

With `composite`, columns are `hex`, `period` (`"2025-04"`) and float32 bands, NaN where a period has no clear observation.

## Pixel chips

```python
@fused.udf
def udf(bounds: fused.types.Bounds = [-95.32, 40.68, -95.30, 40.70]):
    import numpy as np
    chips = fused.catalog.imagery(
        "hls2-s30", bounds, time="2025-06", bands=["red", "nir"],
        output="chip", mask_clouds=True,
    )
    row = chips.iloc[0]
    red, nir = (np.frombuffer(row[b], "<i2").reshape(row.h, row.w).astype("f4") for b in ("red", "nir"))
    return np.where(red == -9999, np.nan, (nir - red) / (nir + red))
```

- Columns `id`, `datetime`, `tile`, `epsg`, `geotransform` (GDAL order, in `epsg`), `h`, `w`, and one bytes column per band.
- With `composite="all", reducer="median"` (a cloud-free median), the rows are per `period` and grid and the bands decode with `"<f4"`, NaN for no data.

## Zonal statistics per polygon

```python
@fused.udf
def udf():
    import geopandas as gpd
    from shapely.geometry import box
    fields = gpd.GeoDataFrame({"field": ["A", "B", "C"]}, geometry=[
        box(-95.3144, 40.6860, -95.3032, 40.6985),
        box(-95.6517, 40.8548, -95.6473, 40.8580),
        box(-95.7258, 40.5847, -95.7164, 40.5936)], crs=4326)
    df = fused.catalog.imagery(
        "hls2-s30", fields, time="2025-06", bands=["red", "nir"],
        output="stats", stats=["mean"],
    )
    lists = df.columns.difference(fields.columns).tolist()
    long = df.drop(columns="geometry").explode(lists, ignore_index=True).infer_objects()
    long["ndvi"] = (long.nir_mean - long.red_mean) / (long.nir_mean + long.red_mean)
    return long.dropna(subset="ndvi")
```

- `df` has one row per polygon, in order: its own columns and geometry, then list columns per date: `date`, `n_px` (the polygon's pixels) and `<band>_<stat>` (NaN when no pixel was clear). The `explode` makes one row per polygon and date.
- Polygons: a GeoDataFrame or GeoSeries (one row each), a list of shapely polygons, or a GeoJSON FeatureCollection (its `properties` become columns); at most 4,096.
- Defaults: `mask_clouds=True`, `composite="day"` with `reducer="median"`, and `stats` of `"mean"`, `"std"`, `"min"`, `"max"`.
- `composite="weekly"`, `"month"`, `"year"` or `"all"` gives one value per period (`date` like `"2025-W23"`, `"2025-06"`); `"none"` takes the scene whose tile covers most of the polygon.

## Arguments

- `bounds`: `(west, south, east, north)` in EPSG:4326, a shapely geometry, a GeoDataFrame or GeoSeries (merged into one area), or a GeoJSON dict. Hex returns cells whose centre is inside; chip pixels outside it are no data. At most 100,000 vertices.
- `time`: `"2025"`, `"2025-06"`, `"2025-06-03"`, `"2025-04/2025-09"` or a `(start, end)` pair with `None` for an open end; inclusive. Without it every date is read.
- `mask_clouds=True`: mask cloud, cloud-adjacent and shadow pixels from `fmask`. Hex drops masked cells and adds `cloud_pct` (masked % of the area per scene); chip sets masked pixels to -9999 and drops scenes with no clear pixel.
- `max_cloud_pct=20`: hex only, needs `mask_clouds=True`; skips scenes more than 20% masked over the area.
- `composite`: `"day"`, `"weekly"`, `"biweekly"`, `"month"`, `"year"` or `"all"`. `reducer`: `"first"` or `"last"` (all bands from one scene), `"median"`, `"mean"`, `"min"` or `"max"` (per band); default `"first"`, and it needs `composite` except with stats.
- Rows add up: one per cell per scene. Narrow `time`, use `composite`, or aggregate with `sql=` to stay inside the UDF time limit.

To browse collections on a canvas and copy a working call, use the `data-catalog` widget (`json-ui-schemas`).
