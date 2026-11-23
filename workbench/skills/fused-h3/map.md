# Showing a hex dataset on a map

A hex dataset that is **indexed** can be drawn with the `fused-map` widget's `fused-hex` layer (tiles, pan-aware), or queried by an `h3-query` widget and drawn from that result (`data: "{{name}}"`), or read directly from the `/h3/query` endpoint by an HTML page that fetches its own data (see [`http.md`](http.md)). The `h3-query` widget, `data` layers, map params, filters and `{{layer_id}}` SQL are in the `json-ui-schemas` skill; a runnable `h3-query` plus map canvas, with the query following the map and a chart cross-filtering it, is in `html-template-nodes`, section "Map with a custom chart".

## End to end

1. **Partition** with `fused.h3.partition(...)` (see `SKILL.md`). Add `chunk_res_offset=3` (about 343 row groups per file; `file_res + chunk_res_offset <= h3_res`) when the zoomed-out overview should draw a finer grid than one cell per file. It aligns every row group to a parent cell, so the overview can draw one cell per chunk. Without it the overview draws one cell per file. The cost is more row groups, a bigger footer and more requests, so skip it for small datasets.
2. **Index** with `fused.h3.index(path, ...)` and wait for `run.tail()`. A dataset that is not indexed is invisible to `/h3/query` and the layer. Re-index after every re-partition.
3. **Map**: add a `fused-hex` layer to a `fused-map`. For several resolutions of one dataset, one per zoom band, add one `composite` layer instead ([Level of detail](#level-of-detail-one-composite-layer)).

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

- `type: "fused-hex"` is never auto-detected: set it. It never auto-fits either: set the map's `centerLng`, `centerLat` and `zoom` on the data (`initialViewState` is not a prop).
- `source.path` is the indexed folder. It sets the endpoint to `/h3/query`, so `source.endpoint` is not needed. The layer also needs `h3Column`, the dataset's hex column (`hex` for anything `fused.h3.partition` wrote).
- ERA5 or gridMET instead of your data: no `path`, and `source.endpoint` set to `/retrieve/era5/daily/bbox` or `/retrieve/gridmet/bbox`, with `dateMin`, `dateMax` and `variables` (see [`http.md`](http.md)).
- `source.dateMin` / `source.dateMax` (ISO) bound the time window. `source.timeColumn` names the time column (set it for `/h3/query` datasets). `source.reduce` collapses each cell's rows over the window: `latest` (default), `first`, `mean`, `min`, `max`, `sum`.
- `source.variables` lists the columns to fetch. Left out, it is the attributes the style, tooltip and filters name.
- `source.limit` and `source.maxRowGroups` cap each tile request. Raise them only for dense data.
- `fillColor` is data-driven with `{"type": "continuous", "attr", "domain"?, "palette"?, "steps"?, "reverse"?, "nullColor"?}`, or `{"type": "categorical", "attr", "colors"?, "palette"?, "nullColor"?}`. Palette names are listed in `reference.md`/the CLI schema.
- `sql` on the layer runs before `reduce`; see `json-ui-schemas`.

### Overview when zoomed out

`source.overview: {}` turns on a zoomed-out view below the layer's zoom floor. It is one request, with no tiles: the server returns either **file cells** (one per indexed file) or, for datasets partitioned with `chunk_res_offset`, **chunk cells** (one per row-group chunk, when there are at most 100,000). Either way, cells carry only row counts, never column values, and by default fill lightly by row count with grey outlines. Zoomed in past the floor, the layer draws rows.

Optional fields: `overview.minZoom` (the overview draws below the floor, default 3) and `overview.extent` (`[west, south, east, north]`, west < east, no antimeridian crossing; also confines row tiles). Restyle it with `style.overview` (`fillColor`, `opacity`, `lineColor`, `lineWidth`, `coverage`). A data-driven `style.overview.fillColor` can only use `row_count_total` or `row_count_window`; any other attr, or `"inherit"` of a data-driven row fill, falls back to the row-count fill.

## Level of detail: one `composite` layer

When the data exists at several pre-aggregated resolutions, one per zoom band (say building counts per res-5 and per res-8 cell zoomed out, the res-12 rows zoomed in), use one `type: "composite"` layer. It holds each resolution as a **level** and draws exactly one at a time. Crossing into another band, the level on screen keeps drawing until the new level has loaded the view, then they swap, so the map never goes blank. Several `fused-hex` layers gated with `minZoom`/`maxZoom` or `visibleMinZoom`/`visibleMaxZoom` blank out at every boundary: do not build level of detail that way.

Each level is its own indexed dataset. Write each coarse level as Parquet with one row per cell and an integer H3 column at that resolution, partition it with `hex_column=` and that `h3_res` (the column becomes `hex`, so one `h3Column` serves every level), and index it, as in steps 1 and 2.

```json
{
  "id": "buildings", "name": "Buildings", "type": "composite", "h3Column": "hex",
  "tooltip": ["hex", "n_buildings"],
  "style": {"opacity": 0.8, "fillColor": {"type": "continuous", "attr": "n_buildings", "palette": "Sunset", "scaleType": "quantile"}},
  "levels": [
    {"name": "res 5", "maxZoom": 8, "source": {"path": "s3://bucket/buildings/hex5/", "variables": ["n_buildings"]}},
    {"name": "res 8", "minZoom": 8, "maxZoom": 12, "source": {"path": "s3://bucket/buildings/hex8/", "variables": ["n_buildings"]}},
    {"name": "buildings", "minZoom": 12, "source": {"path": "s3://bucket/buildings/hex12/", "variables": ["subtype", "height"]},
     "tooltip": ["hex", "subtype", "height"],
     "style": {"fillColor": {"type": "categorical", "attr": "subtype", "palette": "Bold"}}}
  ]
}
```

- A level draws while `minZoom <= map zoom < maxZoom`; an unset end is open. One level draws at a time: where bands overlap the higher `minZoom` wins, and a zoom no band covers draws nothing.
- A level's tiles load from `floor(minZoom)` (0 when unset) up to its `maxZoom`. Keep fine datasets on high bands: a fine level on a low band requests tiles too large for the server.
- Set on the composite, shared by every level: `h3Column`, `style`, `tooltip`, `filters`, `sql`, `legend`, `visible`, `name`. A level may set its own `h3Column` and `tooltip` (they replace the shared ones) and `style` (merged over the shared one key by key; a level's `fillColor` or `lineColor` replaces the shared one whole). Each level keeps its own colour scale.
- `filters` and `sql` apply to whichever level draws. A filter on a column the level does not have is skipped at that level, which still draws. A `sql` that fails at a level (it names a column the level lacks, say) draws that level unqueried.
- Levels are `fused-hex` sources only, read as above (`source.path`, `variables`, `timeColumn`, ...). `source.overview` is ignored on a level: the coarser levels play that role.
- Not a time-playback target.

Pitfalls:

- **Absolute thresholds on aggregates.** A count per cell grows with the cell, so a filter or `sql` such as `n_buildings > 150` keeps most cells at a coarse level and none at a fine one. Threshold a ratio or density instead, or tell the user that each level keeps a different share of cells.
- **A column only some levels have.** A filter on it does nothing at the other levels, a `sql` naming it draws them unqueried, and a widget query naming it fails there. Carry the columns that filters, queries and stats read in every level (and its `source.variables`), or say where they apply.
- **Zoom-gating the levels.** `minZoom`/`maxZoom` on the levels are the bands. Levels take no `visibleMinZoom`/`visibleMaxZoom` (ignored there); on the composite they hide every level at once.
- **Gaps between bands.** Make bands meet: each level's `maxZoom` is the next level's `minZoom`. At a zoom in a gap the layer draws nothing.

### Stats next to the map

A composite is two canvas SQL sources, both read from the level on screen: `{{buildings}}`, the rows loaded for the view (before the layer's `sql` and `filters`), and `{{buildings_drawn}}`, the rows drawn (after them, one per cell). The map's `sourceParam` has an entry for each with `version`, `loading`, `rows`, `error`, `tiles`, plus `level` (index in `levels`) and `band` (`[minZoom, maxZoom]`, null for an open end). A widget in the same node JSON as the map reads them without an edge; another node needs an edge from the map's node.

Give the map `"sourceParam": "map_sources"` and put this `div` beside it in the node's root `div` (`"style": "display:flex;flex-direction:column;height:100%"`, map last with `"style": "flex:1;min-height:0"`):

```json
{"type": "div", "props": {"style": "display:flex;align-items:center;gap:16px;padding:8px;flex:none"}, "children": [
  {"type": "metric", "props": {"label": "Cells drawn", "sql": "SELECT COUNT(*) FROM {{buildings_drawn}}", "format": "comma", "size": 24}},
  {"type": "metric", "props": {"label": "Rows loaded", "sql": "SELECT COUNT(*) FROM {{buildings}}", "format": "comma", "size": 24}},
  {"type": "html", "props": {"style": "flex:1;height:24px", "value": "<div id='lv' style='font:12px sans-serif;color:#aaa'></div><script>function show(p){var s=(p.map_sources||{}).buildings_drawn;if(s)document.getElementById('lv').textContent='level '+s.level+', band '+JSON.stringify(s.band)+', '+s.tiles+' tiles';}fused.params.onChange(show);show(fused.params.getAll());</script>"}}
]}
```

- SQL widgets re-run on their own when a source rebuilds (a swap, a settled view, a query result, a filter edit). Read `sourceParam` only for what SQL cannot give (`level`, `band`, `tiles`), or to re-query with `fused.query` when `version` changes.
- Query only columns every level has: `SUM(n_buildings)` fails while the finest level draws.
- `canvas validate` knows layer ids but not `<id>_drawn`: add `[validate] known_refs = ["buildings_drawn"]` to `canvas.toml`.

## Pitfalls

- **Judging by eye.** Tiles can take 30 s on first load, and a res-11 cell is about one pixel wide at zoom 10. Check with a `metric` on `SELECT COUNT(*) FROM {{<layer id>}}`: the rows in view.
- **Not indexed, or stale index.** Empty maps and 404s usually mean `fused.h3.index` never ran, or the data was re-partitioned afterwards. Re-index.
- **Domain.** Leave `domain` out, or set it to the data's real range. A default like `[0, 100]` on data in `[260, 310]` paints one flat colour.
- **Chunking is all or nothing for a path.** Appending a `chunk_res_offset` partition onto an unchunked output (or the reverse) is refused. Write a new output path and index that.
- **Wrong column name.** `h3Column` must be the dataset's hex column, `fillColor.attr` and `timeColumn` must be real columns.
- **Filtering by partition.** The layer's `source` has no partition filter field. Narrow by time with `dateMin`/`dateMax`, or by value with the layer `sql`. Partition filters are available when calling `/h3/query` directly.
