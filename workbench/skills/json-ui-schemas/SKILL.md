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

- **Containers:** `div`, `form`, `sql-runner` (children: yes)
- **Input:** `text-input`, `text-area`, `number-input`, `datetime-input`, `camera-input`, `color-input`, `dropdown`, `slider`, `button`, `code-editor`, `gallery-input`, `file-upload`, `map-bounds`, `map-h3`
- **Output, display:** `text`, `image`, `video`, `metric`, `iframe`, `html`, `pdf-gallery-viewer`
- **Output, charts:** `bar-chart`, `line-chart`, `stacked-bar-chart`, `stacked-area-chart`, `scatter-chart`, `donut-chart`, `heatmap-chart`
- **Output, tables:** `sql-table`
- **Output, maps:** `fused-map` (mature, use it by default), `kepler-map`, `map` (legacy)
  - To draw an indexed H3 dataset, use a `fused-map` layer of type `fused-hex`: see the `fused-h3` skill's `map.md`.
- **Meta / advanced:** `widget-builder`, `transformer`, `ai-chat`

## `html` and `iframe` widgets vs an HTML template node

- **`html` widget** (`{"type":"html","props":{"value":"<h2>$city</h2>"}}`): a sandboxed iframe inside a JSON-UI layout. It gets `$param` / `{{udf}}` substitution and the same `window.fused` bridge as HTML template nodes (`fused.env`, `fused.params.get/getAll/set/onChange`, `await fused.runPython(udfName, params)`, and `await fused.query(sql, { params, maxRows })`, which runs DuckDB SQL over `{{name}}` sources such as a `fused-map` layer id). Full contract, substitution grammar and pitfalls: the `html-template-nodes` skill. Use the widget for a small custom snippet next to other widgets; use a standalone HTML template node (`.html` file) for a full custom page.
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

- `sql-runner` publishes its result as `{{name}}` to every SQL widget in reach, not only its children: a sibling in the same widget file, a widget on a node with an edge from the runner's node, and `fused.query` in an HTML node with that edge. A widget on a node without that edge does not see it and logs `UDF 'data' is not connected via an edge`. Keep runner names unique across connected nodes: when two are in reach, the first one published wins.
- It caps rows at `maxRows`, 10,000 by default: set it when the UDF returns more (see Known gotchas).
- `fused workbench canvas validate` wrongly flags `{{name}}` as an unknown node.
  `[validate] skip = ["widget_refs"]` in `canvas.toml` works around it, but turns off the whole check: review other `{{name}}` refs by hand.
- Readers reference `{{data}}` (or whatever `name` you set), **not** `{{my_udf}}`.
- The canvas edge (`["my_udf", "widget_node"]`) must also exist in `canvas.toml` for the UDF to be reachable at runtime.
- **The source UDF must have `visible = true` in `canvas.toml`.** Hidden nodes (`visible = false`) do not execute on canvas load and have no cached result. Referencing them in `sql-runner` will fail with: `UDF 'my_udf' has no cached result. Run the UDF first.`

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
- A tiled layer takes a `sql` too (`udf` with `tile: true`, or `fused-hex`): it runs on each tile as it loads, reading the tile's rows as `{{source}}` (a udf layer may also write its own `{{udf}}`). Use it for `WHERE`, computed columns and `GROUP BY` the cell column; the result must keep the cell column (`h3`, `fused-hex`) or the geometry (vector layers). `LIMIT`, `ORDER BY`, `USING SAMPLE` and other UDFs are not available per tile. `raster`, `mvt` and `tileUrl` layers take no `sql`.

  ```json
  {"id": "hot", "type": "fused-hex", "source": {"endpoint": "/retrieve/era5/daily/bbox", "dateMin": "2024-07-01", "dateMax": "2024-07-31", "variables": ["t2m_mean"]},
   "sql": "SELECT * FROM {{source}} WHERE t2m_mean > 300"}
  ```

## `fused-map`: filters bound to params, box select, layers as SQL sources

These need a workbench that includes fusedlabs/application#8451 and #8469 (unstable on 2026-11-05). `fused workbench json-ui validate` against a deployment without them rejects a `"$param"` filter bound; validate with `fused workbench --env <env> json-ui validate` for the deployment you push to. For a complete map plus custom charts that filter each other, see the `html-template-nodes` skill, section "Cross-filtering a map with custom charts".

```json
{
  "type": "fused-map",
  "props": {
    "selectParam": "selected",
    "selectKey": "id",
    "layers": [{
      "id": "listings", "type": "scatterplot", "udf": "{{airbnb_listings}}",
      "latColumn": "lat", "lngColumn": "lng",
      "filters": [
        { "attr": "price", "type": "range", "min": "$p_min", "max": "$p_max" },
        { "attr": "room_type", "type": "categories", "values": "$room_types" }
      ]
    }]
  }
}
```

**Filters bound to params.**

- A range filter's `min` / `max` and a categories filter's `values` take a `"$param"` string in place of a literal. The map reads the param live and filters in the browser.
- While the param is unset, that bound (or that categories filter) is off. A categories filter with an empty list keeps every feature.
- Range bound values are numbers. A param holding `{min, max}` fills both bounds when either bound names it (`"min": "$price", "max": "$price"`). A categories param holds an array.
- Editing a bound filter in the map's sidebar writes the new value to the param, not into the spec, so everything reading the param follows. Removing a bound filter in the sidebar clears its params.
- A feature whose `attr` is missing or null fails an active filter (SQL `BETWEEN` and `IN` drop nulls too).

**Box select: `selectParam` and `selectKey`.**

- `selectParam` names a param the map writes. Shift+drag draws a box and dims the map outside it. Shift+click toggles one feature. Escape or a plain click on the map clears.
- `selectKey` is the property whose values go into `ids`. Default: the cell column (`h3Column`, else `hex`) on hex layers or rows that have one, else `id`. Set it when your id column has another name; without a matching property `ids` stays `[]`.
- The value:

  | Field | Box (shift+drag) | Shift+click | After clearing |
  |---|---|---|---|
  | `mode` | `"box"` | `"click"` | `"none"` |
  | `bbox` | `[west, south, east, north]` | `null` | `null` |
  | `ids` | `selectKey` values of the features the map picked in the box | the clicked features' values | `[]` |
  | `count` | number of picked features | number of clicked features | `0` |
  | `layer`, `key` | layer id, `selectKey` (`null` when the box picked nothing) | same | `null` |
  | `truncated` | `false` | `false` | `false` |

- Filter a box by `bbox`, not by `ids`: picking misses overlapping points (954 ids for a box that held 1,876 rows).
- The selection is session state: it is not saved with the canvas. On a share page it does go into the URL and from there into every UDF run (see `html-template-nodes`, Sharing).

**Layers as SQL sources: `{{layer_id}}`.**

- Each layer of a `fused-map` on the page is a SQL source named by its `id`. Any SQL widget (`bar-chart`, `metric`, `sql-table`, …) and `fused.query` can `SELECT … FROM {{layer_id}}`.
- Reach: the reading widget is in the map's node, or on a node with an edge from the map's node, or on a node with an edge from the layer's UDF.
- A layer id equal to a UDF name shadows that UDF for every SQL widget and `fused.query` in reach. The sidebar's Add layer names a new layer after its UDF, so rename the layer when you also read the UDF itself.
- Rows: for a `udf` layer without `tile`, the UDF's whole result, with neither the layer's `filters` nor its `sql` applied. For a tiled layer (`tile: true`, `fused-hex`), the rows of the tiles loaded now; they change as the view moves.
- The source exists only while its map is on the page. A chart opened alone at `/share/<token>/<chart_node>` shows `UDF 'listings' is not connected via an edge`.
- Until the layer has rows, SQL widgets show loading and `fused.query` rejects `not_ready`.
- `fused workbench canvas validate` flags `{{layer_id}}` as an unknown node, as it does a `sql-runner` name; same workaround.

## Common conventions

- `param` syncs a widget's value with a canvas parameter (or a form field when nested in `form`).
- `sql` fields accept DuckDB queries with `{{source_name}}` and `$param_name` placeholders. Required output columns vary by widget: check the schema. To reuse one SQL result in several widgets, name it with a `sql-runner` and reference that name.
- `$param` values render by type in any widget `sql`: a string is quoted, a number is written as is, an unset param becomes `''`. An array becomes `('a', 'b')` for `IN $list` (`IN ($list)` works too); an empty array becomes `(NULL)` and matches no rows. A `{min, max}` object becomes `min AND max` for `BETWEEN $range`; a missing bound becomes `-1e308` / `1e308`, so use it on numeric columns. Inside a quoted SQL string a `$param` is replaced by its raw text. `fused.query` renders `opts.params` the same way, except that a `$name` missing from `params` rejects (see `html-template-nodes`).
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
