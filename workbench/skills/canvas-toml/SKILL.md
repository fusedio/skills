---
name: canvas-toml
description: Format reference for `canvas.toml` files that define a Fused canvas (nodes, edges, viewport) plus the surrounding folder layout (`{udfName}.py`, `.json`, `.md`, `.html`, `_shared.fused`). Use when creating, editing, or validating any `canvas.toml`, adding/removing UDF nodes, wiring edges, defining folder groupings, or scaffolding a new canvas folder.
---

# Fused canvas folder + `canvas.toml`

> **CLI version:** commands below are written `fused workbench …` (fused ≥ 2.9.3). If `fused workbench` fails with `No such command 'workbench'` (fused 2.9.1 and earlier), drop the word `workbench` — e.g. `fused canvas push`. See `fused-workbench-cli`.

A Fused canvas stored in git is a folder containing one `canvas.toml` plus per-UDF source files. Push to the connected repo and Fused picks up the changes automatically.

## Folder layout

```
my_canvas/
  canvas.toml           # required: layout and node metadata
  udf_0.py              # Python UDF source
  udf_1.py
  widget.json           # optional: JSON-UI widget node (stem = udfName)
  textbox.md            # optional: text / markdown node (stem = udfName)
  page.html             # optional: HTML template node (stem = udfName)
  _shared.fused         # optional: access control
```

- `<name>.py` / `.json` / `.md` / `.html` — source for a node; the **stem must match a node's `udfName`**. The node kind is inferred from the extension (`.py` Python UDF, `.json` JSON-UI widget, `.md` text box, `.html` HTML template node) — there is no `type` key for these in `canvas.toml`.
-- File name stems must be unique in a canvas. The following is OK: `abc.json`, `def.py`. The following will NOT work: `abc.json`, `abc.py`. **The server error for this is misleading** — it says "A UDF with one of those slugs already exists in this collection", which sounds like a cross-canvas naming collision. It's actually caused by the same-stem conflict in your local folder. Fix: delete one of the conflicting files and push again.
-- JSON-UI files: consult the `json-ui-schemas` skill for how to write, validate, and debug them. They contain JSON5.
-- HTML files: consult the `html-template-nodes` skill. The file is stored verbatim (plain HTML/CSS/JS, no Python wrapper); the workbench renders it in a sandboxed iframe with `window.fused` and `$param` / `{{udf}}` substitution.
- `_shared.fused` — omit ⇒ private (author only). Empty file ⇒ team. Set `access_scope = "public"` for public. Set `token = "<value>"` to control the URL slug. This file is honoured on the git-repo sync path; **`fused workbench canvas push` does not apply it** (a pushed canvas stays at its current scope, `team` for a new one) — change the scope in the Workbench share dialog instead.

Do **not** mix `canvas.toml` with the legacy `collection.json` layout in one folder — `canvas.toml` wins if both are present.

## `canvas.toml` example

```toml
type = "canvas"
version = 2
# previewImageUrl = "https://example.com/preview.png"  # optional

[canvas]
edges = [
  ["controls", "udf_0"],   # controls widget drives udf_0 via canvas params
  ["udf_0", "udf_1"],      # udf_1 depends on udf_0's output
]

# One row, 75px gaps: x = previous x + previous width + 75 (see "Layout rules").
[[canvas.nodes]]
udfName = "controls"
description = "Input controls"
title = "Controls"
visible = true
x = 0
y = 0
zIndex = 1
width = 480
height = 700

[[canvas.nodes]]
udfName = "udf_0"
description = "My first UDF"
title = "udf_0"
visible = true
x = 555       # 0 + 480 + 75
y = 0
zIndex = 2
width = 700
height = 500

[[canvas.nodes]]
udfName = "udf_1"
description = "My second UDF"
title = "udf_1"
visible = true
x = 1330      # 555 + 700 + 75
y = 0
zIndex = 3
width = 700
height = 500

[canvas.viewport]
x = 60
y = 60
zoom = 0.6
```

## Top-level fields

| Field | Type | Notes |
|---|---|---|
| `type` | string | Always `"canvas"` |
| `version` | integer | Always `2` |
| `name` | string | Optional display name (server falls back to folder name) |
| `previewImageUrl` | string | Optional preview image URL |

## `[canvas]`

| Field | Type | Notes |
|---|---|---|
| `edges` | array of `[source, target]` pairs | Each pair references `udfName` values |
| `nodes` | array of node tables | See node fields below |
| `viewport` | table | Optional — `x`, `y`, `zoom` |
| `viewportBounds` | table | Optional — `minX`, `minY`, `maxX`, `maxY`; omit when authoring, the workbench derives it |

## `[[canvas.nodes]]`

| Field | Type | Required | Notes |
|---|---|---|---|
| `udfName` | string | yes | Must match a source file stem |
| `x`, `y` | float | yes | Canvas coordinates |
| `zIndex` | integer | yes | Layer order |
| `width`, `height` | integer | yes | Pixel dimensions |
| `description` | string | no | Defaults to `"UDF: <name> (auto)"` |
| `title` | string | no | Defaults to `udfName` |
| `visible` | boolean | no | Output panel visibility; default `true`. **Must be `true` for any UDF referenced via `{{udf_name}}` in a JSON-UI `sql-runner` or via a bare `{{udf_name}}` in an HTML template node.** Hidden nodes do not auto-execute on canvas load, so they have no cached result for widgets to read (an HTML node shows `Loading...` forever). `{{udf?k=v}}` overrides and `fused.runPython` run on demand and do not need this. |
| `type` | string | no | Omit for standard UDF, JSON-UI, text and HTML template nodes (kind comes from the file extension); `"udf-folder"` for folder nodes |
| `textBoxColor` | string | no | Background color for textbox nodes |
| `textBoxGradient` | boolean | no | Textbox gradient toggle |
| `textBoxScaleFactor` | number | no | Textbox content scale |
| `textBoxAlignment` | string | no | Textbox content alignment |

## Folder nodes (`type = "udf-folder"`)

Visual grouping only — child UDFs still live as flat files in the canvas folder.

```toml
[[canvas.nodes]]
type = "udf-folder"
folderName = "Section_1"
folderColor = "#9370DB40"
childUdfOrder = ["udf_0", "udf_1"]
# isLocked = true  # optional, default false
x = 0
y = 0
zIndex = 0
width = 1555    # 40 + 700 + 75 + 700 + 40 — two 700px children in one row
height = 615    # 75 + 500 + 40 (see "Folder geometry")
```

| Field | Notes |
|---|---|
| `folderName` | Display name |
| `folderColor` | Optional hex+alpha color |
| `childUdfOrder` | Ordered `udfName` list for UDFs in this folder |
| `isLocked` | Locks child editing; default `false` |

### Folder geometry — the workbench re-packs folders on load

**The workbench ignores the `x`/`y` you write for folder children and recomputes the folder's `width`/`height`.** On every load it lays the children out in a wrapped grid (in `childUdfOrder`) and resizes the folder to fit them. Consequences:

- Children: still write `x`/`y` (they are required fields) but don't spend effort on them — only `childUdfOrder`, each child's `width`/`height`, and the folder `width` affect the result.
- The folder's on-screen size is **computed**, so a folder you size too small will grow over whatever sits next to or below it. Compute its real size with the formula below and reserve that space in the top-level layout.
- A child's `width`/`height` must be its full node size (including any description text) or the packing is off.

Packing rules (canvas px): side padding `40`, gap between children `75`, top inset `75`, bottom inset `40`. Children fill a row left-to-right and wrap when the next child would cross `width - 40`.

```
usable width = width - 80
row fits N children of width W when  40 + N*W + (N-1)*75 + 40 <= width
folder width  = max(width, widest child + 80)
folder height = 75 + Σ(row heights) + 75*(rows - 1) + 40
```

The folder's name tag renders *above* the box (outside `height`), so always leave the full 75px row gap above a folder.

Worked example — four 700×500 UDFs:

| Folder `width` | Children per row | Rows | Computed height |
|---|---|---|---|
| 1555 | 2 | 2 | 75 + 500 + 75 + 500 + 40 = **1190** |
| 2330 | 3 | 2 | **1190** (second row holds one) |
| 3105 | 4 | 1 | 75 + 500 + 40 = **615** |

Pick the folder `width` to get the row count you want, write the computed `height`, and place the next top-level row at `folder.y + computed height + 75`. Nested folders are allowed; treat an inner folder as a child whose size is its own computed size.

## Canvas architecture patterns

### Loader / analysis split

Separate expensive data fetching from the analysis that uses it. Put the expensive call in a hidden `fetch_*` or `load_*` UDF so it caches independently of the analysis parameters. The visible analysis UDFs call it via `fused.load()`:

```
[fetch_data]  (hidden, visible=false, cached)
      ↓  fused.load("fetch_data")()
[analyze_data]  (visible — lightweight, re-runs fast when params change)
      ↓
[display_widget]  (visible — JSON widget or map)
```

```python
# fetch_data.py — hidden, cached, no parameters that change often
@fused.udf(cache_max_age="1h")
def udf(source_url: str = "s3://..."):
    import pandas as pd
    return pd.read_parquet(source_url)   # slow — cached for 1 hour

# analyze_data.py — visible, fast, re-runs on every slider/dropdown change
@fused.udf
def udf(threshold: float = 0.5, region: str = "north"):
    df = fused.load("fetch_data")()      # returns instantly from cache
    return df[df['value'] > threshold]
```

This pattern means the user can scrub an interactive control without re-fetching the data source each time.

### Single-item + parallel batch dual mode

Design the per-item UDF to work as a standalone visible node, then add a separate orchestrator that fans it out. This gives you two working paths in the same canvas:

```
[single_item_analysis]   ← single-item, visible, good for debugging
[batch_analysis]         ← orchestrator, calls single_item_analysis.map(items)
```

Keep the single-item UDF as the source of truth. The orchestrator is just:

```python
@fused.udf
def udf(items_csv: str = "a,b,c"):
    worker = fused.load("single_item_analysis")
    items = [x.strip() for x in items_csv.split(",")]
    return worker.map(items).df()
```

The worker UDF must include the item identifier as a column in its output — after `.df()` concatenates all results, you need to know which rows came from which item.

## Authoring rules

- Ephemeral UI state (selection, sidebar) is **not** stored — only nodes, edges, viewport.
- When adding a node: create the `.py` / `.json` / `.md` / `.html` file **and** add a matching `[[canvas.nodes]]` entry with the same stem, plus the edges it needs.
- When removing a node: delete its source file(s) **and** its node entry, plus any `edges` referencing it.
- UDFs can call each other via `fused.load("<udfName>")`. For multiprocessing, split into a new UDF.
- Before pushing, run `fused workbench canvas validate ./my_canvas` (push runs it too; `--no-validate` skips). It checks every node has a source file, every edge endpoint is a node, orphaned files, widget JSON parse, `{{ref}}` names inside `.json` widgets, and widget `param` names against connected UDF signatures. Suppress a check with `--skip <check>` or a `[validate] skip = ["orphaned_files"]` table in `canvas.toml`.

### Testing UDFs that call sibling canvas UDFs

When a UDF uses `fused.load("other_udf")` to call a sibling UDF within the same canvas, **local testing with `fused.load("my_udf.py")` will fail** with a "UDF not found" error. The local file context has no canvas, so the runtime cannot resolve sibling UDF names.

The correct testing approach:
1. Push the canvas first: `fused workbench canvas push ./my_canvas`
2. Then test the pushed UDF by name: `fused.load("my_udf")()`

Running by name resolves the UDF from the server with full canvas context, so `fused.load("other_udf")` inside it can find its sibling.

## Canvas naming

Canvas names (used in `fused workbench canvas push --canvas` and the URL slug) must contain **only letters, numbers, and underscores** — spaces and hyphens are rejected with a 422 error. Use the optional `name` field in `canvas.toml` for a human-readable display name; it is separate from the URL slug.

```toml
name = "My Demo Canvas"   # display name — spaces OK here
```

```sh
# slug — underscores only
fused workbench canvas push ./my_canvas --canvas "my_demo_canvas"
```

## Edges — rules and common mistakes

`edges` serve two purposes: (1) **visual data-flow arrows** users see in the canvas, and (2) **canvas parameter propagation** (values set by a widget/node that downstream UDFs must receive).

**`edges = []` is almost never correct for a multi-node canvas.** An empty edge list means no connections are visible and no parameter propagation *from other nodes* — any UDF that should react to a widget or upstream UDF's output will run in isolation. The only legitimate case for `edges = []` is a canvas where every node is fully independent (no shared params from another node, no data dependencies).

**Critical: `fused.load()` does NOT create canvas edges.** When a UDF calls `fused.load("other_udf")` internally, that is a Python-level import — it has nothing to do with canvas edges. You still must add an explicit edge in `canvas.toml` for both data-flow visualization and parameter propagation. Do not write `edges = []` just because UDFs chain via `fused.load()`.

**When to add an edge from A → B:**
- Node B reads a canvas parameter (`lat`, `zoom`, any shared param) that is set by node A (e.g. a widget node)
- Node B calls `fused.load("a")` internally — add `["a", "b"]` to show the dependency visually
- Node B's output logically depends on node A's output

**Edge syntax** — each entry is `["sourceUdfName", "targetUdfName"]`. Using the template example above:

```toml
[canvas]
edges = [
  ["controls", "udf_0"],   # controls widget drives udf_0 via canvas params
  ["udf_0", "udf_1"],      # udf_1 calls fused.load("udf_0") internally
]
```

**Practical checklist before finalizing `canvas.toml`:**
1. For every widget/controls node: does it have an edge to each UDF it drives? If not, canvas params won't propagate.
2. For every `fused.load("x")` call in UDF `b`: is `["x", "b"]` in `edges`? If not, the dependency is invisible to users.
3. Is `edges` still `[]` with more than one node? If yes, verify every node is truly independent — this is almost certainly wrong.
4. For every HTML template node: does every `{{name}}` / `fused.runPython("name")` in the `.html` have an edge `["name", "<html_node>"]`, and every `fused.params.set("p", …)` an edge to each UDF that takes `p`? `fused workbench canvas validate` does not check `.html` files — grep them yourself.

For JSON-UI widget nodes that reference a UDF via `{{udf_name}}` SQL (typically via `sql-runner`), also add an edge from that UDF node to the widget node: `edges = [["my_udf", "my_widget"]]`. Without the edge, the UDF data is not reachable at runtime.

**HTML template nodes follow the same rule, in both directions.** An HTML node can only see params from, inline `{{udf}}` output of, and `fused.runPython()` against UDF nodes that have an edge into it (bidirectional edges count both ways). Add:
- `["my_udf", "my_page"]` for every UDF the page references with `{{my_udf}}` or `fused.runPython("my_udf", ...)`. Missing edge ⇒ `runPython` rejects with `not_allowed`, `fused.params.get` is `undefined`, `{{my_udf}}` renders empty.
- `["my_page", "target_udf"]` for every UDF the page drives with `fused.params.set(...)` — the param only propagates along edges.

The workbench UI infers edges from `{{udf}}` placeholders and literal `fused.runPython("name")` calls when nodes are created there, but `canvas.toml` is explicit: write them all. See the `html-template-nodes` skill for the full runtime contract.

## Layout rules

Nothing in the CLI or server lays nodes out — the coordinates you write are exactly what the user sees. Overlapping nodes are the most common defect in generated canvases, so lay the canvas out deliberately: **rows, a fixed gap, and arithmetic, never eyeballed numbers.**

### Node sizes

`width`/`height` are canvas pixels. Use these defaults unless the content needs otherwise:

| Node type | Width | Height |
|---|---|---|
| Python UDF | 700 | 500 |
| JSON-UI inputs / controls panel | 480 | 700 |
| Text box (`.md`) | 350 | 250 |
| HTML template node | content width (800 for a dashboard) | content height (600 for a dashboard) — the iframe fills the node exactly, so the page must fit or scroll internally |
| Folder | computed — see "Folder geometry" | computed — see "Folder geometry" |

### Placement algorithm

1. **Gap is 75px** everywhere (between columns, between rows, around folders). This matches the workbench's own spacing; 30–50px looks cramped and the node chrome collides.
2. **Start at the origin.** First node at `x = 0, y = 0`; no negative or huge coordinates.
3. **Lay out in rows, left to right, in data-flow order** (controls → loaders → analysis → display) so edges run left-to-right. Each node's `x = previous x + previous width + 75`.
4. **Wrap after ~3 nodes or ~2500px of row width.** Next row starts at `x = 0`, `y = previous row y + tallest node in that row + 75`. A row's height is its tallest node, not the node above.
5. **Text boxes are nodes too** — give them a slot in the row (typically first, as a title/intro) or their own row above. Never drop a note on top of a UDF.
6. **Folders occupy their computed size**, not the size you'd like. Compute it (Folder geometry), place the folder as one item in the row, and advance `x`/`y` by that computed size.
7. **Check before finishing:** for every pair of top-level nodes, the rectangles `[x, x+width] × [y, y+height]` must not intersect, and no top-level node may fall inside a folder's computed rectangle. Fix any intersection by moving the node to the next row — do not shrink nodes to fit.

Worked example — controls + two UDFs + a folder of four UDFs + a note:

```
row 0 (y = 0):   note 350×250 @ (0,0)   controls 480×700 @ (425,0)   udf_a 700×500 @ (980,0)   udf_b 700×500 @ (1755,0)
                 row height = 700  →  next row y = 775
row 1 (y = 775): folder width 1555, 2 per row, 2 rows → computed height 1190  @ (0,775)
                 next row y = 775 + 1190 + 75 = 2040
```

### Viewport

The viewport is a pan/zoom transform, not a point: on screen, `screen = canvas * zoom + (x, y)`. With a layout that starts at the origin:

- `zoom = min(1, 1300 / total layout width)` — fits the whole canvas into a typical window; clamp to no less than `0.3`.
- `x = 60`, `y = 60` — a small margin so the first node isn't flush with the edge.

Omit `[canvas.viewportBounds]`; the workbench derives it.
