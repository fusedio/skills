---
name: fused-runtime
description: What a Fused UDF can import and shell out to at run time — the Python packages and versions in the realtime and batch images, system binaries, DuckDB extensions, and how to get a package that isn't installed. Use before importing a library in a UDF, when a UDF fails with ModuleNotFoundError or a version-specific API error, or when choosing between libraries for a UDF.
---

# The Fused UDF runtime

A UDF runs in one of two prebuilt images. Both are Python **3.12** on linux x86_64, CPU only. There is no per-UDF `requirements`; what the image has is what the UDF gets.

| Engine | Image | Notes |
|---|---|---|
| default (`engine` unset / `"realtime"`), `udf.map()` workers | **realtime** | ~700 packages; includes the AI extra (torch CPU, torchvision, onnxruntime, segment-geospatial, geoai) |
| `engine="medium"` / `"large"`, other instance jobs | **batch** | ~620 packages; no torchvision/onnxruntime/datasets/geoai |

## Checking a package

[`packages.md`](packages.md) lists every installed package with its version in each image, plus a by-category view and the packages whose versions differ between images. Grep it instead of reading it:

```bash
grep -iE "^\| (polars|rioxarray) \|" packages.md
```

A package absent from that file is not installed: `import` it and the UDF fails. To confirm from inside a UDF:

```python
from importlib.metadata import version
version("polars")
```

## Version traps

- **polars is 1.x in realtime and 0.20 in batch.** APIs renamed in polars 1.0 break on `engine="medium"/"large"`: `join(how="full")` is `how="outer"` in 0.20, and `pivot(on=...)` is `pivot(columns=...)`. In a UDF that may run on both engines, check `pl.__version__` or use pandas/DuckDB.
- **torch is the CPU build** in both images. There is no CUDA anywhere.
- Commonly assumed but **not installed**: tensorflow, keras, jax, lightgbm, catboost, langchain, altair, lonboard, h3ronpy, deltalake, pyiceberg, kerchunk, dask-geopandas, streamlit, pyspark. Pick an installed alternative (scikit-learn/xgboost, plotly/pydeck, `h3` + DuckDB, pyarrow).

## DuckDB extensions

None are preinstalled, and the default DuckDB home directory isn't reliably writable (Lambda allows writes only under `/tmp`). Point `home_directory` at `/tmp` before installing (needs outbound network):

```python
import duckdb
con = duckdb.connect()
con.sql("""
    SET home_directory='/tmp/duckdb/';
    INSTALL h3 FROM community; LOAD h3;
    INSTALL spatial; LOAD spatial;
    INSTALL httpfs; LOAD httpfs;
""")
```

The public `common` UDF module wraps this with caching: `fused.load("https://github.com/fusedio/udfs/tree/<sha>/public/common/").duckdb_connect()` loads h3, spatial and httpfs.

## System binaries

Both images ship the GDAL CLI (`gdalinfo`, `ogr2ogr`, `gdal_translate`, …), `ffmpeg`, `tippecanoe`, `pmtiles`, `wgrib2`, `pdal`, `git`, `node`/`npm`, `unrar`, and `uv`. Realtime also has `jq` and `aws`. Call them with `subprocess.run([...], check=True)`.

## A package isn't installed

1. **Use an installed alternative** (see the categories in `packages.md`). This is almost always the right move.
2. **Ask Fused to add it** to the image. Say which engine needs it.
3. **Install onto the shared mount (unofficial).** `/mount` is a disk shared across an org's UDFs, and `uv` is on the PATH. Pure-Python packages work best; compiled packages must match Python 3.12 and the pinned numpy/pyarrow:

   ```python
   @fused.udf
   def udf():
       import subprocess, sys
       target = "/mount/envs/my_env"
       subprocess.run(["uv", "pip", "install", "--python", sys.executable,
                       "--target", target, "some-package==1.2.3"], check=True)
       sys.path.insert(0, target)
       import some_package
   ```

   Install once, then keep only the `sys.path.insert`. docs.fused.io's Dependencies page shows a `python3.11` site-packages path; the runtime is 3.12, so build any env for 3.12.
4. **Custom batch image**: `image_name=` on batch jobs pulls a custom image, but only in environments where Fused has enabled custom images (otherwise the server returns 403). There is no custom image for realtime.
