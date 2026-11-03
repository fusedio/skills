# Showing a hex dataset on a map

A hex dataset that is **indexed** can be drawn with the `fused-map` widget's `fused-hex` layer, or read directly from the `/h3/query` endpoint by a widget or HTML page that fetches its own data. For the widget's other props, see the `json-ui-schemas` skill.

## End to end

1. **Partition** with `fused.h3.partition(...)` (see `SKILL.md`). Add `chunk_res_offset=3` (about 343 row groups per file; `file_res + chunk_res_offset <= h3_res`) when the map should show a zoomed-out overview of the *values*, not just where files are. It aligns every row group to a parent cell, so the server can summarise each cell cheaply. Without it the overview can only outline files. The cost is more row groups, a bigger footer and more requests, so skip it for small datasets.
2. **Index** with `fused.h3.index(path, ...)` and wait for `run.tail()`. A dataset that is not indexed is invisible to `/h3/query` and the layer. Re-index after every re-partition.
3. **Map**: add a `fused-hex` layer to a `fused-map`.

## Minimal `fused-map` config

```json
{
  "type": "fused-map",
  "props": {
    "style": "height:100%",
    "layers": [{
      "id": "hex",
      "type": "fused-hex",
      "h3Column": "hex",
      "source": {
        "path": "s3://bucket/hex/stations/",
        "timeColumn": "date",
        "overview": {}
      },
      "style": {
        "fillColor": {"type": "continuous", "attr": "temp", "palette": "Viridis"},
        "opacity": 0.8
      }
    }]
  }
}
```

- `type: "fused-hex"` is never auto-detected: set it.
- `source.path` is the indexed folder. It sets the endpoint to `/h3/query`, so `source.endpoint` is not needed. The layer also needs `h3Column`, the dataset's hex column (`hex` for anything `fused.h3.partition` wrote).
- `source.dateMin` / `source.dateMax` (ISO) bound the time window. `source.timeColumn` names the time column (set it for `/h3/query` datasets). `source.reduce` collapses each cell's rows over the window: `latest` (default), `first`, `mean`, `min`, `max`, `sum`.
- `source.variables` lists the columns to fetch. Left out, it is the attributes the style, tooltip and filters name.
- `source.limit` and `source.maxRowGroups` cap each tile request. Raise them only for dense data.
- `fillColor` is data-driven with `{"type": "continuous", "attr", "domain"?, "palette"?, "steps"?, "reverse"?, "nullColor"?}`, or `{"type": "categorical", "attr", "colors"?, "palette"?, "nullColor"?}`. Palette names are listed in `reference.md`/the CLI schema.
- `sql` on the layer runs per tile on `{{source}}` and must keep the cell column. See `json-ui-schemas`.
- `retrieve` endpoints (`/retrieve/era5/...`, `/retrieve/gridmet/bbox`) serve the published ERA5 and GridMET datasets instead. They need `dateMin` and `dateMax`; see `datasets.md`.

### Overview when zoomed out

`source.overview: {}` turns on a zoomed-out view below the layer's zoom floor. It is one request, with no tiles: the server returns either **file cells** (one per indexed file) or, for datasets partitioned with `chunk_res_offset`, **chunk cells** coloured by the layer's own `fillColor` attr (each cell's max). Zoomed in past the floor, the layer draws rows.

Optional fields: `overview.minZoom` (the overview draws below the floor, default 3) and `overview.extent` (`[west, south, east, north]`, west < east, no antimeridian crossing; also confines row tiles). Restyle it with `style.overview` (`fillColor`, `opacity`, `lineColor`, `lineWidth`, `coverage`). `style.overview.fillColor: "inherit"` takes the row fill, but a data-driven one draws no overview and warns on the layer card for file cells, which can only be coloured by `row_count_total` or `row_count_window`.

## Calling `/h3/query` directly

For an HTML widget or script that fetches its own data, call `GET /h3/query` on the Fused server with a bearer token (public `s3://` locations can be read anonymously).

| Param | Meaning |
|---|---|
| `path` | Indexed location (required). |
| spatial selector | At most one of: `cell` (hex string, every row under that cell), `lat` + `lng`, `min_lng`/`min_lat`/`max_lng`/`max_lat`, or `hex_min` + `hex_max` (inclusive hex-string range). None returns every row. |
| `time_min`, `time_max` | Inclusive ISO datetimes. |
| `columns` | Subset of columns, repeated (`columns=a&columns=b`). Omitted returns all. |
| `partition` | JSON object of column to value or list of values, e.g. `{"scenario": ["ssp245","ssp585"], "date": "2050-01"}`. |
| `partition_range` | JSON object of column to inclusive `[min, max]`, `null` for an open end, e.g. `{"date": ["2050-01", "2050-06"]}`. |
| `format` | `parquet` (default), `index`, `stats` or `files`, below. |
| `max_row_groups`, `cursor` | Paging. Big results come back a page at a time; follow `X-Fused-Next-Cursor` (parquet) or `next_cursor` (body) until it is gone. |

Formats:

- `parquet`: matching rows as a Parquet file. Decode it in the browser with a Parquet reader (hyparquet, parquet-wasm).
- `files`: JSON `{files, h3_resolution, chunk_resolution, row_counts}`. `files` are the lowercase hex cells the matching files are named by. `chunk_resolution` is null unless the dataset was partitioned with `chunk_res_offset`. `row_counts` maps each file to `{total, window}`. No file is opened, so it is fast: use it to outline coverage.
- `stats`: per-row-group min and max for `columns` (required) plus each group's H3 range, a small response for a coarse overview.
- `index`: an opaque read plan for the Fused client libraries. Not a stable format: use `fused.h3.query` instead of parsing it.

From Python, `fused.h3.query` (see `SKILL.md`) wraps this.

## Pitfalls

- **Not indexed, or stale index.** Empty maps and 404s usually mean `fused.h3.index` never ran, or the data was re-partitioned afterwards. Re-index.
- **Domain.** Leave `domain` out, or set it to the data's real range. A default like `[0, 100]` on data in `[260, 310]` paints one flat colour.
- **Chunking is all or nothing for a path.** Appending a `chunk_res_offset` partition onto an unchunked output (or the reverse) is refused. Write a new output path and index that.
- **Wrong column name.** `h3Column` must be the dataset's hex column, `fillColor.attr` and `timeColumn` must be real columns.
- **Filtering by partition.** The layer's `source` has no partition filter field. Narrow by time with `dateMin`/`dateMax`, or by value with the layer `sql`. Partition filters are available when calling `/h3/query` directly.
