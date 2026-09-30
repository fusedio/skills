---
name: json-ui-schemas
description: JSON schemas for Fused canvas UI widget components (text, text-input, button, dropdown, charts, maps, sql-table, form, transformer, etc.). Use when authoring or editing widget JSON files (e.g. `widget_*.json` in canvas directories), validating widget props, or answering questions about which fields a given widget type accepts.
---

# Fused JSON UI widget schemas

Reference for every supported widget `type` and its prop schema.

The full JSON Schema for each component (with descriptions, defaults, required fields, and enum values) is available from the fused CLI. See the `fused-cli` skill for how to read it. Read it before authoring or modifying widget JSON.

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

- **Layout / containers:** `div`, `form`, `sql-runner` (children: yes)
- **Inputs:** `text-input`, `text-area`, `number-input`, `datetime-input`, `camera-input`, `color-input`, `dropdown`, `slider`, `button`, `code-editor`, `gallery-input`
- **Display:** `text`, `image`, `metric`, `iframe`, `html`
- **Charts:** `bar-chart`, `line-chart`, `stacked-bar-chart`, `stacked-area-chart`, `scatter-chart`, `donut-chart`, `heatmap-chart`
- **Tables:** `sql-table`
- **Maps:** `map`, `map-bounds`, `map-h3`, `fused-map`
- **Meta / advanced:** `widget-builder`, `transformer`, `ai-chat`

## `html` and `iframe` widgets vs an HTML template node

- **`html` widget** (`{"type":"html","props":{"value":"<h2>$city</h2>"}}`): a sandboxed iframe inside a JSON-UI layout. It gets `$param` / `{{udf}}` substitution and the same `window.fused` bridge as HTML template nodes (`fused.env`, `fused.params.get/getAll/set/onChange`, `await fused.runPython(udfName, params)`). **The CLI schema (`fused workbench json-ui schemas html`) still describes an older `fusedCanvas.setParam` API for this widget — that API is gone; use `window.fused`.** `reference.md` was hand-corrected; running `scripts/generate_json_ui_reference.py` will revert it until the CLI ships the new schema text. Full contract, substitution grammar and pitfalls: the `workbench:html-template-nodes` skill. Use the widget for a small custom snippet next to other widgets; use a standalone HTML template node (`.html` file) for a full custom page.
- **`iframe` widget**: embeds a URL or an HTML-returning UDF (`src: "{{my_udf}}"`); no scripting against the canvas. Use it to show a UDF-generated page (folium, plotly `to_html`, …) or an external site.
- Edges apply to all three: the source UDF needs an edge into the widget's node.

## Accessing UDF data — use `sql-runner`

When a JSON-UI node needs to read data from a canvas UDF, always use `sql-runner` as the root (or a wrapping ancestor). Do **not** put `{{udf_name}}` SQL directly on a leaf widget at the root — it does not resolve reliably without a `sql-runner` ancestor.

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

- `sql-runner` fetches the UDF output once and exposes it as `{{name}}` to all descendants.
- Descendants reference `{{data}}` (or whatever `name` you set), **not** `{{my_udf}}`.
- The canvas edge (`["my_udf", "widget_node"]`) must also exist in `canvas.toml` for the UDF to be reachable at runtime.
- **The source UDF must have `visible = true` in `canvas.toml`.** Hidden nodes (`visible = false`) do not execute on canvas load and have no cached result. Referencing them in `sql-runner` will fail with: `UDF 'my_udf' has no cached result. Run the UDF first.`

## Common conventions

- `param` syncs a widget's value with a canvas parameter (or a form field when nested in `form`).
- `sql` fields accept DuckDB queries with `{{source_name}}` and `$param_name` placeholders. Required output columns vary by widget — check the schema. When referencing a canvas UDF's data, use `sql-runner` and reference its `name` in descendant SQL, rather than `{{udf_name}}` directly.
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
4. Validate with `fused workbench json-ui validate <file>` — unknown keys and missing required props will be flagged.

## Debugging widgets with the Fused CLI

The `fused workbench json-ui` subcommands are the fastest way to check your work without round-tripping through the canvas UI. See the `workbench:fused-cli` skill for full flag details; the common debugging flow is:

- **Verify the schema you're targeting** — `fused workbench json-ui schemas <type>` prints the live JSON Schema for one or more component types (or all of them if omitted). Use this when `reference.md` and the CLI disagree; the CLI is authoritative.
- **Validate a widget JSON before pushing** — `fused workbench json-ui validate path/to/widget_foo.json` (or a path to a `.json5` file, or an inline JSON5 string). Run this after every non-trivial edit; it catches missing required props, unknown keys, and bad enum values without needing a canvas push.
- **See a widget rendered without opening a browser tab** — once the canvas is shared (`fused workbench canvas share <ref>`), use `fused workbench json-ui run-shared-widget <share-token> <widget-name> --screenshot-filename out.png` to render the widget headlessly and save a PNG. Add `--wait N` if the widget loads data asynchronously. `run-inline-widget` does the same for an inline JSON5 config string, which is useful for iterating on a widget that isn't committed yet.
- **Refresh the catalog** — `fused workbench json-ui catalog-prompt` prints the high-level component catalog; handy when a new widget type appears in the CLI before it lands in `reference.md`.

Recommended loop when authoring a new widget JSON: write → `fused workbench json-ui validate <file>` → fix → push → confirm it renders.

**Always verify the widget renders correctly** before reporting the task complete. Use one of these methods:

- **CLI (preferred for quick iteration):** `fused workbench json-ui run-shared-widget <share-token> <widget-name> --screenshot-filename out.png` — renders headlessly and saves a PNG. Review the PNG to confirm layout, labels, and data look correct.
- **Browser:** open the canvas URL and interact with the widget directly. This is required when testing interactivity (dropdowns, form submission, map panning, etc.) that a screenshot cannot capture.

Do not claim success after `validate` alone — validation only checks schema conformance, not runtime behavior or visual correctness.
