---
name: json-ui-schemas
description: JSON schemas for Fused canvas UI widget components (text, text-input, button, dropdown, charts, maps, sql-table, form, transformer, etc.). Use when authoring or editing widget JSON files (e.g. `widget_*.json` in canvas directories), validating widget props, or answering questions about which fields a given widget type accepts.
---

# Fused JSON UI widget schemas

> **CLI version:** commands below are written `fused workbench …` (only the 2.9.2b0+ pre-releases have this namespace; released versions such as 2.9.1 and 2.9.3 don't). If `fused workbench` fails with `No such command 'workbench'`, drop the word `workbench` — e.g. `fused canvas push`. See `fused-workbench-cli`.

Reference for every supported widget `type` and its prop schema.

The full JSON Schema for each component (with descriptions, defaults, required fields, and enum values) is available from the fused CLI. See the `fused-workbench-cli` skill for how to read it. Read it before authoring or modifying widget JSON.

The authoritative reference to JSON schema is available from the CLI. There is also a reference in `reference.md`, but it is an offline copy that may be out of date.

JSON UI files are in JSON5 format, which may have trailing commas, comments, etc.

## Widget node structure

Every widget in a JSON UI file follows this envelope:

```json
{
  "type": "<widget-type>",
  "props": {
    /* ALL component properties go here: value, sql, param, style, label, chart options, etc. */
  },
  "children": [
    /* child widget nodes — only valid for container types: div, form, sql-runner */
  ]
}
```

**Critical rules:**
- ALL component properties (`value`, `sql`, `param`, `style`, `label`, chart options, etc.) MUST be nested under `"props"`. Never place them directly on the node object.
- `"children"` is an array of widget nodes. Only container types (`div`, `form`, `sql-runner`) accept children. Omit it for leaf widgets.
- The top-level JSON UI file is itself a widget node (typically a root `div`).

**Minimal correct example:**

```json
{
  "type": "div",
  "props": { "style": "display:flex;flex-direction:column;gap:16px;padding:20px" },
  "children": [
    {
      "type": "text",
      "props": { "value": "Hello World", "variant": "h2", "style": "color:#fff" }
    },
    {
      "type": "dropdown",
      "props": {
        "label": "City",
        "param": "city",
        "sql": "SELECT city AS value, city AS label FROM {{my_udf}} ORDER BY 1",
        "nullable": true
      }
    }
  ]
}
```

**Common mistake — WRONG:**
```json
{ "type": "text", "value": "Hello", "style": "color:#fff" }
```
**Correct:**
```json
{ "type": "text", "props": { "value": "Hello", "style": "color:#fff" } }
```

## Available widget types

Input widgets set canvas params (edge: widget → UDF). Output widgets show a UDF result (edge: UDF → widget).

- **Containers:** `div`, `form`, `sql-runner`, `h3-query` (children: yes)
- **Input:** `text-input`, `text-area`, `number-input`, `datetime-input`, `camera-input`, `color-input`, `dropdown`, `slider`, `button`, `code-editor`, `gallery-input`, `file-upload`, `map-bounds`, `map-h3`
- **Output, display:** `text`, `image`, `video`, `metric`, `iframe`, `html`, `pdf-gallery-viewer`
- **Output, charts:** `bar-chart`, `line-chart`, `stacked-bar-chart`, `stacked-area-chart`, `scatter-chart`, `donut-chart`, `heatmap-chart`
- **Output, tables:** `sql-table`
- **Output, maps:** `fused-map` (mature, use it by default), `kepler-map`, `map` (legacy)
  - To draw an indexed H3 dataset, use a `fused-map` layer of type `fused-hex` (tiles, pan-aware), or an `h3-query` widget's result as a layer (`data: "{{name}}"`, refetched only when its params change): see the `fused-h3` skill's `map.md`.
- **Meta / advanced:** `widget-builder`, `transformer`, `ai-chat`

## `html` and `iframe` widgets vs an HTML template node

- **`html` widget** (`{"type":"html","props":{"value":"<h2>$city</h2>"}}`): a sandboxed iframe inside a JSON-UI layout. It gets `$param` / `{{udf}}` substitution and the same `window.fused` bridge as HTML template nodes (`fused.params`, `fused.runPython`, `fused.query`). Full contract, substitution grammar and pitfalls: the `html-template-nodes` skill. Use the widget for a small custom snippet next to other widgets; use a standalone HTML template node (`.html` file) for a full custom page.
- **`iframe` widget**: embeds a URL or an HTML-returning UDF (`src: "{{my_udf}}"`); no scripting against the canvas. Use it to show a UDF-generated page (folium, plotly `to_html`, …) or an external site.
- **`<fused-widget>` inside an HTML node**: the reverse direction, a JSON-UI widget inside a custom page. The element's text is a widget spec from this skill (`{"type":…,"props":{…}}`); the workbench renders it over the element's box with the HTML node's edges and identity. Details in the `html-template-nodes` skill, section "Embedding widgets".
- Edges apply to all three: the source UDF needs an edge into the widget's node.

## `sql-runner`: one named SQL result for other widgets

Widgets can query `{{udf_name}}` directly. A UDF runs once per page, however many widgets read it.
A `sql-runner` names one SQL result. Its SQL can read several UDFs, and runners can nest.

**Correct pattern:**

```json
{
  "type": "sql-runner",
  "props": {
    "sql": "SELECT * FROM {{my_udf}}",
    "name": "data"
  },
  "children": [
    {
      "type": "metric",
      "props": {
        "label": "Row Count",
        "sql": "SELECT COUNT(*) FROM {{data}}",
        "format": "comma"
      }
    }
  ]
}
```

- `sql-runner` publishes its result as `{{name}}` to every SQL widget in reach, not only its children: a sibling in the same widget file, a widget on a node with an edge from the runner's node, and `fused.query` in an HTML node with that edge. A widget on a node without that edge does not see it and logs `'data' is not connected via an edge`. Keep runner names unique across connected nodes: when two are in reach, the first one published wins.
- It caps rows at `maxRows`, 10,000 by default: set it when the UDF returns more (see Known gotchas).
- `fused workbench canvas validate` wrongly flags `{{name}}` as an unknown node.
  `[validate] skip = ["widget_refs"]` in `canvas.toml` works around it, but turns off the whole check: review other `{{name}}` refs by hand.
- Readers reference `{{data}}` (or whatever `name` you set), **not** `{{my_udf}}`.
- The canvas edge (`["my_udf", "widget_node"]`) must also exist in `canvas.toml` for the UDF to be reachable at runtime.
- **The source UDF must have `visible = true` in `canvas.toml`.** Hidden nodes (`visible = false`) do not execute on canvas load and have no cached result. Referencing them in `sql-runner` will fail with: `UDF 'my_udf' has no cached result. Run the UDF first.`

## `h3-query`: an indexed H3 dataset query as a named SQL source

One `GET /h3/query` (or any endpoint speaking its parameters), its Parquet result landed in the browser's DuckDB and published as `{{name}}`, exactly like a `sql-runner` result. It shows nothing itself: put the rows on screen with a SQL widget (`sql-table`, a chart, `metric`) or a `fused-map` layer, and one `h3-query` can feed several. Readers: any SQL widget or `fused-map` in the same node (child or sibling), or on a node with an edge from this node.

```json
{
  "type": "h3-query",
  "props": {
    "name": "h3_rows",
    "path": "s3://bucket/hex/stations/",
    "minLng": -122.6, "minLat": 37.6, "maxLng": -122.2, "maxLat": 37.9,
    "timeMin": "2024-07-01", "timeMax": "2024-07-01",
    "columns": ["hex", "temp"]
  },
  "children": [
    { "type": "sql-table", "props": { "sql": "SELECT * FROM {{h3_rows}} LIMIT 100" } }
  ]
}
```

- `name` is what readers reference (`{{h3_rows}}`), not the node name.
- `path` (required): the indexed dataset, sent as `path=`. `endpoint` (optional): where the query goes, default `/h3/query` on the current server; a full URL elsewhere gets no token.
- `columns` lists every column returned: include `hex` when a map draws the rows.
- At most one spatial selector: `cell`, `lat`+`lng`, the four bbox edges, or `hexMin`+`hexMax`; none reads the whole dataset.
- Every string or number prop accepts `$param` (`"timeMin": "$date"`); the query waits until it is set and re-runs when it changes. Params come from the same node or a node with an edge into it. `"columns": "$cols"` takes an array or a comma-separated string, so a dropdown value like `"hex,t2m_max"` picks the variable.
- To follow a map's view, split its `param` bounds into four params: `html-template-nodes` skill, "Map with a custom chart", which is also the runnable `h3-query` canvas.
- The whole result stays in browser memory (`maxPages`, default 16, caps it). For large or pan-aware data use a `fused-map` `fused-hex` layer instead.
- No UDF runs; no `visible = true` requirement; `fused workbench canvas validate` may flag `{{name}}` as unknown (see `sql-runner`).

## `fused-map`: a layer from a canvas SQL source (`data: "{{name}}"`)

A layer can draw the rows a canvas SQL source already holds instead of running a UDF:

```json
{ "id": "hex", "type": "h3", "h3Column": "hex", "data": "{{h3_rows}}",
  "style": { "fillColor": { "type": "continuous", "attr": "temp" } } }
```

- `{{name}}` is an `h3-query` or `sql-runner` widget's `name`, or another map's layer id. The layer draws its rows as they are and draws again when the source is published again; panning does not refetch.
- Edge: from the publishing node to the map's node. The workbench adds it for an `h3-query` or `sql-runner` name; add it yourself for another map's layer id.
- `data` is otherwise inline GeoJSON. `sql` may be added on top (`{{source}}` or `{{h3_rows}}` reads the rows). Row layers only (`geojson`, `h3`, `scatterplot`, `heatmap`, `arc`, or `type` omitted); not with `tile`, `udf` or `tileUrl`, nor on `raster`, `mvt`, `fused-hex`.
- A layer other than `fused-hex` with no `data`, `sql`, `udf` or `tileUrl` is an error and never drawn.

## Inputs driving a `fused-map` tile layer

To let viewers change a tile UDF's arguments, put the inputs and the map in one widget and pass the inputs into the layer's `udf` placeholder with `$param`. The map re-requests its tiles whenever a value changes.

```json
{
  "type": "div",
  "props": { "style": "display:flex;flex-direction:column;gap:8px;height:100%" },
  "children": [
    { "type": "number-input", "props": { "label": "Band", "param": "band", "defaultValue": 0 } },
    {
      "type": "fused-map",
      "props": {
        "style": "flex:1;min-height:0",
        "layers": [{
          "id": "tiles", "type": "raster", "tile": true, "minZoom": 12,
          "udf": "{{my_tile_udf?band_index=$band}}"
        }]
      }
    }
  ]
}
```

- The only edge needed is UDF → widget (`["my_tile_udf", "my_widget"]`, where `my_widget` is the widget's node name in `canvas.toml`). A widget → UDF edge is not needed.
- Give every input a `defaultValue`, so `$param` has a value on the first load.
- The input's `param` name and the UDF argument name can be different (`band_index=$band`).
- No `sql-runner` is needed: a `fused-map` layer's `udf` runs the UDF directly.
- A tiled layer takes a `sql` too (`udf` with `tile: true`, or `fused-hex`): one `SELECT` (a `WITH` is fine) over the rows of every tile in view, read as `{{source}}`. It runs again on pan, zoom or a `$param` change, without refetching tiles. The result must keep the cell column (`h3`, `fused-hex`) or the geometry (vector layers). `raster`, `mvt` and `tileUrl` layers take no `sql`.

  ```json
  {"id": "hot", "type": "fused-hex", "h3Column": "hex", "source": {"path": "s3://bucket/hex/stations/", "timeColumn": "date", "variables": ["temp"]},
   "sql": "SELECT * FROM {{source}} WHERE temp > 30"}
  ```

## `fused-map`: params it writes, filters bound to params, layers as SQL sources

Pages and widgets read these params with `fused.params` or `$param`; a page writes only `selectParam` back. All of them are used together in the `html-template-nodes` skill, section "Map with a custom chart". "Saved" means kept with the canvas and restored on reload.

- `param`: the view's `[west, south, east, north]`. Sent once when the map is ready, then on pans with `autoSend` (after `autoSendDebounceMs`, default 600). Saved.
- `clickParam`: the clicked feature's properties, only the layer's `tooltip` fields when it lists them. Saved.
- `hoverParam`: the same for the feature under the cursor, at most once per frame; removed when the cursor leaves every feature. Not saved.
- `selectParam`: `{ layer, key, ids, count, bbox, mode, truncated }`. Shift+drag draws a box (`mode: "box"`; filter by `bbox`), shift+click toggles a feature (`"click"`, `bbox: null`; filter by `ids`), Escape or a plain click clears (`"none"`). `ids` are `selectKey` values (default: the cell column on hex layers, else `id`). Not saved. The page the map is in, or a node with an edge to or from it, can write it: `null` clears the box and the dimming, `{ bbox: [west, south, east, north] }` draws that box.
- `stateParam`: layer overrides and the camera, `view: { centerLng, centerLat, zoom, bearing, pitch, width, height }` (`zoom` in 512 px Web Mercator tiles, `width` / `height` in CSS px): enough to project lng/lat to map pixels. `view` is written when a gesture ends and is absent until the first one. Saved.
- `sourceParam`: `{ [layerId]: { version, loading, rows, error } }`. Re-query a layer when its `version` changes (`!==`, not `>`); `version` is 0 until the layer has rows. Not saved.

**Filters bound to params.** A range filter's `min` / `max` or a categories filter's `values` can be a `"$param"`: `{"attr": "temp", "type": "range", "min": "$lo", "max": "$hi"}`. The map applies it live in the browser. An unset param turns that bound (or that categories filter) off, a `{min, max}` param fills each bound that names it, and a categories list of `[]` keeps every feature. Editing a bound filter in the sidebar writes the param.

**Layers as SQL sources: `{{layer_id}}`.**

- Each layer is a SQL source named by its `id`, for SQL widgets and `fused.query` in the map's node or page, on a node with an edge from the map's node, or on one with an edge from the layer's UDF. A layer id equal to a UDF name shadows that UDF.
- A `udf` layer's source is the UDF's whole result. A cell-tiled layer's (`fused-hex`, or `h3` with `tile: true`) is every row of the tiles in view, one per cell per time step, typed as in the Parquet (a timestamp stays `TIMESTAMP`), with the cell column as a lowercase hex string; it is empty below the layer's `minZoom`. Both are read before the layer's `sql`, `filters` and `source.reduce`. Other tiled layers hold the tiles loaded.
- Until a layer first has rows, SQL widgets show loading and `fused.query` rejects `not_ready`. After that a rebuild (pan, param change) keeps serving the previous rows. The source exists only while the map is mounted.
- `fused workbench canvas validate` flags `{{layer_id}}` as an unknown node, as it does a `sql-runner` name; same workaround.

## Common conventions

- `param` syncs a widget's value with a canvas parameter (or a form field when nested in `form`).
- `sql` fields accept DuckDB queries with `{{source_name}}` and `$param_name` placeholders. Required output columns vary by widget: check the schema. To reuse one SQL result in several widgets, name it with a `sql-runner` and reference that name.
- `$param` values render by type in any widget `sql`: a string is quoted, a number is written as is, an unset param becomes `''`. An array becomes `('a', 'b')` for `IN $list` (`IN ($list)` works too); an empty array becomes `(NULL)` and matches no rows. A `{min, max}` object becomes `min AND max` for `BETWEEN $range`; a missing bound becomes `-1e308` / `1e308`, so use it on numeric columns. Inside a quoted SQL string a `$param` is replaced by its raw text. `fused.query` renders `opts.params` the same way.
- `style` is always a CSS string (`"padding: 8px; color: red"`), not an object.
- Charts default `barColor`/`lineColor` to Fused lime yellow (`#E8FF59`).

## Layout and height gotcha

Widgets render inside containers with dynamic height. Flex properties (`flex:1`, `flex-grow`, `min-height:0`, `overflow`) only work reliably when the parent has an explicit height or a complete height chain up to a sized ancestor. Without that, flex children may collapse, overflow, or expand unexpectedly.

**Rule of thumb:** If a chart, table, or map inside a `div` looks collapsed or missing, set an explicit `height` or `min-height` on the parent `div` first.

```json
{
  "type": "div",
  "props": { "style": "display:flex;gap:16px;height:400px" },
  "children": [
    {
      "type": "bar-chart",
      "props": {
        "sql": "SELECT label, value FROM {{my_udf}}",
        "style": "flex:1;min-width:0"
      }
    }
  ]
}
```

Without `height:400px` on the parent `div`, `flex:1` on the chart has nothing to fill and the chart collapses.

## Known gotchas

### `form` — top-level `param` bundles all children into one JSON object
If `form` has a top-level `"param"`, all child values are broadcast as a single JSON object. Remove the top-level `param` so each child broadcasts individually as its own canvas param.

### `sql-runner` — default `maxRows` of 10,000 silently truncates large datasets
`sql-runner` defaults to `maxRows: 10000`. If the source UDF returns more than 10,000 rows, all child widgets (`metric`, `sql-table`, `line-chart`, etc.) silently operate on only the first 10,000 rows and produce wrong results — for example, a `COUNT(*)` metric returns exactly `10000` instead of the real total.

Always set `maxRows` explicitly on `sql-runner` when the source UDF may return more than 10k rows:

```json
{
  "type": "sql-runner",
  "props": {
    "sql": "SELECT * FROM {{my_udf}}",
    "name": "data",
    "maxRows": 500000
  }
}
```

## How to use this skill

1. Open `reference.md` and find the section for the widget `type` you're working with.
2. Honor `required` props and respect `enum` constraints.
3. When constructing a widget JSON, prefer SQL-driven options/data over static when a UDF is available.
4. Validate with `fused workbench json-ui validate <file>`. It flags missing required props, bad enums and props outside `props`, not unknown prop keys.

## Debugging widgets with the Fused CLI

The `fused workbench json-ui` subcommands are the fastest way to check your work without round-tripping through the canvas UI. See the `fused-workbench-cli` skill for full flag details; the common debugging flow is:

- **Verify the schema you're targeting** — `fused workbench json-ui schemas <type>` prints the live JSON Schema for one or more component types (or all of them if omitted). Use this when `reference.md` and the CLI disagree; the CLI is authoritative.
- **Validate a widget JSON before pushing** — `fused workbench json-ui validate path/to/widget_foo.json` (or a path to a `.json5` file, or an inline JSON5 string). Run this after every non-trivial edit; it catches missing required props, bad enum values and props outside `props` (not unknown prop keys) without needing a canvas push.
- **See a widget rendered without opening a browser tab** — once the canvas is shared (`fused workbench canvas share <ref>`), use `fused workbench json-ui run-shared-widget <share-token> <widget-name> --screenshot-filename out.png` to render the widget headlessly and save a PNG. Add `--wait N` if the widget loads data asynchronously. `run-inline-widget` does the same for an inline JSON5 config string, which is useful for iterating on a widget that isn't committed yet.
- **Refresh the catalog** — `fused workbench json-ui catalog-prompt` prints the high-level component catalog; handy when a new widget type appears in the CLI before it lands in `reference.md`.

Recommended loop when authoring a new widget JSON: write → `fused workbench json-ui validate <file>` → fix → push → confirm it renders.

**Always verify the widget renders correctly** before reporting the task complete. Use one of these methods:

- **CLI (preferred for quick iteration):** `fused workbench json-ui run-shared-widget <share-token> <widget-name> --screenshot-filename out.png` — renders headlessly and saves a PNG. Review the PNG to confirm layout, labels, and data look correct.
- **Browser:** open the canvas URL and interact with the widget directly. This is required when testing interactivity (dropdowns, form submission, map panning, etc.) that a screenshot cannot capture.

Do not claim success after `validate` alone — validation only checks schema conformance, not runtime behavior or visual correctness.
