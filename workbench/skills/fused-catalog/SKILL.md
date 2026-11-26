---
name: fused-catalog
description: Read satellite and raster collections in a UDF with `fused.catalog`. `fused.catalog.list()` lists the collections (Harmonized Landsat Sentinel-2 `hls2-s30` and `hls2-l30`, elevation, land cover and more) with their bands and date ranges; `fused.catalog.imagery()` reads one over a box, a geometry or a GeoDataFrame of polygons and dates as H3 cells (`output="hex"`), pixel chips (`output="chip"`) or zonal statistics per polygon (`output="stats"`), with cloud masking, a per-scene cloud limit and day, weekly, monthly or yearly composites. Use when a UDF needs Sentinel-2 or Landsat reflectance, NDVI or another band index, a cloud-free composite, a per-field time series, or when code mentions `fused.catalog`.
---

# Reading imagery with `fused.catalog`

`fused.catalog.imagery` returns a DataFrame for a collection, area and dates: no STAC search, no COG reads. Call it inside a UDF. `help(fused.catalog.imagery)` is the full reference.

```python
fused.catalog.imagery(
    collection, bounds, time=None, bands=None, mask_clouds=None, h3_res=None, sql=None, *,
    max_cloud_pct=100, composite=None, reducer=None, output="hex", stats=None, return_timings=False,
)
```

## Collections

`fused.catalog.list()` has one row per collection: `name`, `bands`, `time_min`, `time_max`, `has_cloud_mask`.

- `hls2-s30` (Sentinel-2) and `hls2-l30` (Landsat): 30 m, bands such as `red`, `green`, `blue`, `nir`, `swir1`, `swir2` as int16 reflectance scaled by 10,000 (-9999 no data), plus the `fmask` cloud mask.
- Always pass `bands=`: the default is every band but `fmask`, view angles included.
- Elevation, land cover and other rasters read the same way: `fused.catalog.imagery("cop-dem-glo-30", bounds)` returns `hex`, `data`.

## Arguments

- `bounds`: a box `(west, south, east, north)` in EPSG:4326, a shapely geometry or a GeoJSON geometry (at most 100,000 vertices). For several polygons, a GeoDataFrame, GeoSeries, list of shapely geometries or GeoJSON FeatureCollection (at most 4,096): every output then works per polygon. A frame in another CRS is reprojected to EPSG:4326 for the call and returned as given.
- `time`: `"2025"`, `"2025-06"`, `"2025-06-03"`, `"2025-04/2025-09"` or a `(start, end)` pair with `None` for an open end; inclusive.
- `mask_clouds`: masks cloud, cloud-adjacent and shadow pixels from `fmask`. Off by default for hex and chip, on for stats.
- `max_cloud_pct`: drops a scene whose cloud, adjacent and shadow pixels are more than this percentage of its pixels with data in the area (each polygon on its own). Default 100 keeps every scene.
- `composite` and `reducer`: one value per period instead of per scene (see Composites).
- `sql`: DuckDB over the result (table `df`) before it is returned, e.g. `sql="select date, avg(nir) nir from df group by 1"`.

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
    df = fused.catalog.imagery(
        "hls2-s30", bounds, time="2025-04/2025-09", bands=["red", "nir"],
        mask_clouds=True, composite="month", reducer="median",
    )
    df["ndvi"] = (df.nir - df.red) / (df.nir + df.red)
    return df
```

- With `composite`: `hex`, `date` (the 1st of each month here) and float32 bands; about 72k rows for this 2 km box and six months.
- Without: one row per cell and scene, `hex`, the bands as stored (int16), `date` (the scene time, only when `time` is given) and, with masking, `cloud_pct`. Masked cells are dropped.
- Each cell takes the pixel under its centre, not an average. `h3_res` defaults to the pixel size (12 for 30 m); a coarser `h3_res=10` samples, so aggregate finer cells to average.

## Pixel chips

```python
@fused.udf
def udf(bounds: fused.types.Bounds = [-95.32, 40.68, -95.30, 40.70]):
    import numpy as np
    chips = fused.catalog.imagery(
        "hls2-s30", bounds, time="2025-06", bands=["red", "nir"],
        output="chip", mask_clouds=True, max_cloud_pct=20,
    )
    row = chips.iloc[0]
    red, nir = (np.frombuffer(row[b], "<i2").reshape(row.h, row.w).astype("f4") for b in ("red", "nir"))
    return np.where(red == -9999, np.nan, (nir - red) / (nir + red))
```

- Columns `id`, `date`, `tile`, `epsg`, `geotransform` (GDAL order, in `epsg`), `h`, `w`, and one bytes column per band. Masked pixels and pixels outside a geometry are no data (-9999 for reflectance); with masking, scenes with no clear pixel are dropped.
- With `composite="all", reducer="median"` (a cloud-free median), the rows are per `date` and grid and the bands decode with `"<f4"`, NaN for no data.

## Zonal statistics

```python
@fused.udf
def udf(bounds: fused.types.Bounds = [-95.32, 40.68, -95.30, 40.70]):
    return fused.catalog.imagery(
        "hls2-s30", bounds, time="2025-06", bands=["red", "nir"], output="stats", stats=["mean"],
    )
```

A one-row GeoDataFrame: `geometry`, then lists in date order: `date`, `n_px` (the polygon's pixels) and `<band>_<stat>` (NaN on a date with no clear pixel). Defaults: `composite="day"`, `reducer="median"`, `stats` of `"mean"`, `"std"`, `"min"`, `"max"`.

Several polygons, one row each with the caller's columns:

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
        output="stats", stats=["mean"], max_cloud_pct=20,
    )
    lists = ["date", "n_px", "red_mean", "nir_mean"]
    long = df.drop(columns="geometry").explode(lists, ignore_index=True).infer_objects()
    long["ndvi"] = (long.nir_mean - long.red_mean) / (long.nir_mean + long.red_mean)
    return long
```

The `explode` makes one row per field and date.

## Composites

`composite` reduces the scenes of each period to one value per cell, pixel or polygon. `date` is a UTC timestamp of the period's start:

| `composite` | `date` |
|---|---|
| `"none"` (default for hex and chip) | the scene time |
| `"day"` (default for stats) | midnight UTC |
| `"weekly"` | the ISO week's Monday |
| `"biweekly"` | the first Monday of a pair of ISO weeks (W01 and W02, ...; W53 alone) |
| `"month"` | the 1st |
| `"year"` | 1 January |
| `"all"` | null |

`reducer`: `"first"` (default) or `"last"` take all bands from one scene; `"median"` (stats default), `"mean"`, `"min"` and `"max"` combine each band. It needs `composite` except with stats. A scene counts only where every requested band is valid. With stats, `"none"` takes per date the scene whose tile holds most of the polygon.

## Gotchas

- `max_cloud_pct` below 100 needs masking: hex and chip raise `ValueError` without `mask_clouds=True`; stats masks by default.
- A scene over `max_cloud_pct` is dropped before any composite. Where HLS tiles overlap, each satellite pass counts once in a composite, from another tile's copy if one was dropped. Without a composite, hex and chip give a row per tile there.
- A period's `date` can be before the start of `time` (the ISO week of 1 April 2025 starts 31 March); only scenes inside `time` are read.
- Without `time`, hex reads every date and has no `date` column.
- Several polygons give a GeoDataFrame for every output: one row per polygon, in order, its own columns (a name clash gets `_input`), then each output column as a list. Each must be a Polygon: `explode()` multi-part ones first. `sql` there sees `i`, the polygon's position: keep it in the select to get the lists back.
- Rows add up: one per cell per scene. Narrow `time`, use `composite`, or aggregate with `sql=` to stay inside the UDF time limit.

To browse collections on a canvas and copy a working call, use the `data-catalog` widget (`json-ui-schemas`).
