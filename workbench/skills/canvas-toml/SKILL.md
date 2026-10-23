---
name: canvas-toml
description: Format reference for `canvas.toml` files that define a Fused canvas (nodes, edges, viewport) plus the surrounding folder layout (`{udfName}.py`, `.json`, `.md`, `.html`, `_shared.fused`). Use when creating, editing, or validating any `canvas.toml`, adding/removing UDF nodes, wiring edges, defining folder groupings, or scaffolding a new canvas folder.
---

# Fused canvas folder + `canvas.toml`

> **CLI version:** commands below are written `fused workbench …` (only the 2.9.2b0+ pre-releases have this namespace; released versions such as 2.9.1 and 2.9.3 don't). If `fused workbench` fails with `No such command 'workbench'`, drop the word `workbench` — e.g. `fused canvas push`. See `fused-workbench-cli`.

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

# One row, 75px gaps: x = previous x + previous width + 75. Let
# scripts/canvas_layout.py fix compute these numbers (see "Layout rules").
[[canvas.nodes]]
udfName = "controls"
description = "Input controls"
nodeDescriptionScaleFactor = 1.5
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
nodeDescriptionScaleFactor = 1.5
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
nodeDescriptionScaleFactor = 1.5
title = "udf_1"
visible = true
x = 1330      # 555 + 700 + 75
y = 0
zIndex = 3
width = 700
height = 500

# No [canvas.viewport]: the workbench fits all nodes into view on load (see "Viewport").
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
| `viewport` | table | Optional — `x`, `y`, `zoom`. Written by the workbench; **ignored on load** (the editor fit-views all nodes). Omit |
| `viewportBounds` | table | Optional — `minX`, `minY`, `maxX`, `maxY` in canvas px. Frames the *share view* on open; omit unless you want a specific framing |

## `[[canvas.nodes]]`

| Field | Type | Required | Notes |
|---|---|---|---|
| `udfName` | string | yes | Must match a source file stem (folder nodes: any unique id, no file) |
| `x`, `y` | float | yes | Canvas coordinates |
| `zIndex` | integer | no | Layer order. Missing ⇒ node index + 1. The workbench gives the first node of a new canvas `100`, then `max + 1`. Folders are usually `0` |
| `width`, `height` | integer | yes | Size of the node **body** in canvas px. The description panel is drawn *below* the body and is not part of `height` (see "Description panel") |
| `description` | string | no | Markdown shown in a panel under the node. Default is empty. (Strings like `"UDF: <name> (auto)"` are synthetic placeholders and are stripped on export — never write them) |
| `nodeDescriptionScaleFactor` | number | no | Font scale of the description panel. The workbench writes `1.5` on every new node; write it too so the panel height matches |
| `title` | string | no | Defaults to `udfName` |
| `visible` | boolean | no | Output panel visibility; default `true`. **Must be `true` for any UDF referenced via `{{udf_name}}` in a JSON-UI `sql-runner` or via a bare `{{udf_name}}` in an HTML template node.** Hidden nodes do not auto-execute on canvas load, so they have no cached result for widgets to read (an HTML node shows `Loading...` forever). `{{udf?k=v}}` overrides and `fused.runPython` run on demand and do not need this. |
| `type` | string | no | Omit for standard UDF, JSON-UI, text and HTML template nodes (kind comes from the file extension); `"udf-folder"` for folder nodes |
| `textBoxColor` | string | no | Background color for textbox nodes |
| `textBoxGradient` | boolean | no | Textbox gradient toggle |
| `textBoxScaleFactor` | number | no | Textbox content scale |
| `textBoxAlignment` | string | no | Textbox content alignment |
| `widgetBackgroundColor` | string | no | Background color for JSON-UI widget nodes |

Not stored in `canvas.toml` (the TOML path drops them, so never write them): `isCollapsed`, `folderPadding`, `folderGap` (the folder spacing presets). After a push/pull every folder packs with the default `40` padding / `75` gap.

## Folder nodes (`type = "udf-folder"`)

Visual grouping only — children still live as flat files in the canvas folder and keep their own `[[canvas.nodes]]` entries. Any file-backed node can be a child (`.py`, `.json`, `.md`, `.html`). **Folders cannot be nested through `canvas.toml`**: a folder listed in another folder's `childUdfOrder` is ignored by the workbench and rendered top-level at its own `x`/`y` (usually on top of something). Use sibling folders instead.

```toml
[[canvas.nodes]]
type = "udf-folder"
udfName = "Section_1"        # folder id — no source file; spaces allowed
folderName = "Section_1"
folderColor = "#9370DB40"
childUdfOrder = ["udf_0", "udf_1"]
# isLocked = true  # optional, default false
x = 0
y = 0
zIndex = 0
width = 1555    # 40 + 700 + 75 + 700 + 40 — two 700px children in one row
height = 615    # 75 + 500 + 40 (see "Folder geometry")

[[canvas.nodes]]
udfName = "udf_0"
x = 40          # child x/y are folder-relative (and recomputed on load anyway)
y = 75
zIndex = 1
width = 700
height = 500
```

| Field | Notes |
|---|---|
| `udfName` | Folder id. Use the same string as `folderName` |
| `folderName` | Display name |
| `folderColor` | Optional hex+alpha color |
| `childUdfOrder` | Ordered `udfName` list of children (file-backed nodes only — never another folder). A node absent from every `childUdfOrder` is top-level |
| `isLocked` | Locks child editing; default `false` |

`validate` accepts folder nodes without a source file but **does not check `childUdfOrder`** — a misspelled child passes validation. Diff the list against every node's `udfName` yourself (folder ids have no file stem).

### Folder geometry — the workbench re-packs folders on load

**The workbench ignores the `x`/`y` you write for folder children and recomputes the folder's `width`/`height`.** On every load it lays the children out in a wrapped grid (in `childUdfOrder`) and resizes the folder to fit them. Consequences:

- Children: still write `x`/`y` (they are required fields) but don't spend effort on them — only `childUdfOrder`, each child's `width`/`height`, and the folder `width` affect the result.
- The folder's on-screen size is **computed**, so a folder you size too small will grow over whatever sits next to or below it. Compute its real size with the formula below and reserve that space in the top-level layout.
- A child with a `description` is **taller than its `height`**: the workbench measures the description panel and adds it when packing (see "Description panel"). One line ≈ 44 px, two lines ≈ 75 px. So a folder of described nodes is taller than the bare formula says.

**Do not do this arithmetic by hand — run `scripts/canvas_layout.py` (see "Deterministic layout tools").** The rules, for reading the output:

Packing rules (canvas px): side padding `40`, gap between children `75`, top inset `75`, bottom inset `40`. Children fill a row left-to-right in `childUdfOrder` and wrap when the next child would cross `width - 40` (the first child of a row never wraps, even if it is wider than the folder).

```
child height  = height + description panel height (0 when no description)
usable width  = width - 80
row fits N children of width W when  40 + N*W + (N-1)*75 + 40 <= width
row height    = tallest child height in that row
folder width  = max(round(width), widest child + 80, 200)
folder height = 75 + Σ(row heights) + 75*(rows - 1) + 40
```

The folder's name tag renders *above* the box (outside `height`), so always leave the full 75px row gap above a folder.

Worked example — four 700×500 UDFs:

| Folder `width` | Children per row | Rows | Computed height |
|---|---|---|---|
| 1555 | 2 | 2 | 75 + 500 + 75 + 500 + 40 = **1190** |
| 2330 | 3 | 2 | **1190** (second row holds one) |
| 3105 | 4 | 1 | 75 + 500 + 40 = **615** |

Pick the folder `width` to get the row count you want, write the computed `height`, and place the next top-level row at `folder.y + computed height + 75`. No nesting: every folder is a top-level item of the row layout.

A complete, script-checked canvas with sibling folders, descriptions, a note, widgets and an HTML node is in `examples/folders/` next to this file. Copy its shape; regenerate its numbers with `canvas_layout.py fix`.

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
- **Input widget → consumer:** A is a widget that only sets params (slider, dropdown, form) and B is the UDF or widget that reads them.
- **UDF → output widget:** A is a UDF and B is a widget that shows its result through `{{a}}` (map, chart, table, iframe). A widget whose inputs feed its own `{{a?arg=$param}}` is an output widget, so this one edge is enough.
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
1. For every input widget: does it have an edge to each UDF it drives? If not, canvas params won't propagate.
2. For every `fused.load("x")` call in UDF `b`: is `["x", "b"]` in `edges`? If not, the dependency is invisible to users.
3. Is `edges` still `[]` with more than one node? If yes, verify every node is truly independent — this is almost certainly wrong.
4. For every HTML template node: does every `{{name}}` / `fused.runPython("name")` in the `.html` have an edge `["name", "<html_node>"]`, and every `fused.params.set("p", …)` an edge to each UDF that takes `p`? `fused workbench canvas validate` does not check `.html` files — grep them yourself.

**HTML template nodes follow the same rule, in both directions.** An HTML node can only see params from, inline `{{udf}}` output of, and `fused.runPython()` against UDF nodes that have an edge into it (bidirectional edges count both ways). Add:
- `["my_udf", "my_page"]` for every UDF the page references with `{{my_udf}}` or `fused.runPython("my_udf", ...)`. Missing edge ⇒ `runPython` rejects with `not_allowed`, `fused.params.get` is `undefined`, `{{my_udf}}` renders empty.
- `["my_page", "target_udf"]` for every UDF the page drives with `fused.params.set(...)` — the param only propagates along edges.

The workbench UI infers edges from `{{udf}}` placeholders and literal `fused.runPython("name")` calls when nodes are created there, but `canvas.toml` is explicit: write them all. See the `html-template-nodes` skill for the full runtime contract.

## Layout rules

Nothing in the CLI or server lays nodes out — the coordinates you write are exactly what the user sees (folders are the one exception: the workbench re-packs their children on load). Overlapping nodes are the most common defect in generated canvases, and the workbench highlights overlapping nodes, so an overlap is a visible bug. Lay the canvas out with **rows, a fixed gap, and the script below — never eyeballed numbers.**

### Deterministic layout tools — `scripts/canvas_layout.py`

The script next to this skill is a port of the workbench's own layout code (`folder-layout.ts`, `auto-arrange.ts`, `node-placement.ts`), checked against canvases the workbench saved. Use it instead of computing sizes and positions yourself. Needs Python 3.11+ (`python3.12 …` or `uv run --python 3.12 …` if `python3` is older); no extra packages.

```sh
SCRIPT=<this skill folder>/scripts/canvas_layout.py

python3 $SCRIPT check ./my_canvas          # overlaps, folder sizes the workbench will change (exit 1 on errors)
python3 $SCRIPT fix ./my_canvas            # re-pack folders + snap rows/columns to 75px gaps, then re-check
python3 $SCRIPT fix ./my_canvas --arrange  # ...or re-flow the top level like the workbench's auto-arrange
python3 $SCRIPT folder-size --width 1555 --children 700x500,700x500x1,700x500   # WxH or WxHxDESCLINES
python3 $SCRIPT place ./my_canvas --near load_data --direction right --size 700x500
python3 $SCRIPT place ./my_canvas --center 1200,800 --size 350x250
```

Workflow when authoring or editing a canvas:

1. Write every node with its real `width`/`height`. Give top-level nodes a **row intent** only: nodes you want on the same row get the same `y`, rows get increasing `y`, columns increasing `x` (rough numbers are fine). Folder children: any `x`/`y`, e.g. `0`.
2. Run `fix`. It rewrites `canvas.toml` in place: folders get their packed `width`/`height` and child positions, top-level rows get `y = previous row bottom + 75` and columns `x = previous right + 75`, where "bottom" includes folder packing and description panels. Comments in the file are not kept — keep notes in `.md` nodes, not TOML comments.
3. Run `check` (also run by `fix`). Ship only when it prints `ok`. `fused workbench canvas validate` does **not** check layout.
4. Adding one node to an existing canvas: `place --near <node>` gives the slot the workbench itself would use (right, then below, above, left); `place --center x,y` spirals out from a point the way the toolbar "add node" does. Then `check`.

`check` output levels: `error` = the workbench will show something different from your file (overlap, folder size); `warn` = probable visual problem (description panel runs into a neighbour, negative coordinates); `info` = harmless (child x/y differ from the packed position).

### Node sizes

`width`/`height` are canvas px for the node **body**. The workbench creates nodes at these sizes; use them unless the content needs otherwise:

| Node type | Workbench default | Notes |
|---|---|---|
| Python UDF (`.py`) | 700 × 500 | |
| JSON-UI widget (`.json`) | 700 × 500 | A narrow controls column (e.g. 480 × 500) is a fine choice, but it is a choice, not a default |
| HTML template node (`.html`) | 700 × 500 | The iframe fills the node exactly; size to the page (800 × 600 for a dashboard) or make the page scroll |
| Text box (`.md`) | 350 × 250 | No description panel |
| Folder | computed | See "Folder geometry" |

### Description panel

A node's `description` renders in a panel **below** the body, outside `height`, 4 px under the node, full node width, text at `14 × nodeDescriptionScaleFactor` px (21 px at the default 1.5) with line-height 1.5:

```
panel height ≈ 12 + lines × 31.5      → 1 line ≈ 44 px, 2 lines ≈ 75 px, 3 lines ≈ 107 px
lines ≈ ceil(characters / (width / 11.5))  per paragraph, at scale 1.5   (700 px wide ≈ 60 characters per line)
```

The workbench measures the real panel and adds it to the child height when packing folders, so folders grow with descriptions. For top-level rows nothing adds it for you: the row height must be `max(height + panel)` of the row, otherwise a two-line description runs into the row below (the 75 px gap hides a one-line panel, not more). The script does both. Keep descriptions to one line where you can; put longer text in a `.md` node.

### Placement algorithm (what the script does, for reading its output)

1. **Gap is 75 px** everywhere: between columns, between rows, inside folders. This is the workbench's own spacing constant.
2. **Start at the origin.** First node at `x = 0, y = 0`; no negative coordinates.
3. **Rows, left to right, in data-flow order** (controls → loaders → analysis → display) so edges run left-to-right. `x = previous x + previous width + 75`.
4. **Row height = tallest item in the row** (body + description panel, or a folder's computed size). Next row `y = row y + row height + 75`.
5. **Wrap** when a row gets wider than about 3 UDF nodes (the workbench's auto-arrange wraps at `average node width × 3.5`; `fix --arrange` uses exactly that rule).
6. **Text boxes are nodes too** — give them a slot (typically first, as a title/intro).
7. **Folders occupy their computed size**, not the size you wrote; the script writes the computed size back.
8. **No two top-level rectangles may intersect** (touching edges are fine), and no top-level node may fall inside a folder's rectangle.

How the workbench itself places nodes (so hand-made layouts feel native):

- *New node from the toolbar*: centred in the current view, then spiralling out (right, below, left, above, diagonals) in steps of node size + 75 until a free slot.
- *Duplicate / "connect to create"*: right of the source (+75), else below, above, left, then the corners.
- *Auto-arrange (toolbar)*: rows from the selection's top-left, wrap at `average width × 3.5`, row height = tallest, UDF-list order, sticky notes last; folder children are skipped (the folder re-packs itself).
- *Drop into a folder*: the node is appended to `childUdfOrder` and the folder re-packs.

### Viewport

The workbench editor **ignores `[canvas.viewport]`**: on load it always fits all nodes into view. The share view (`/canvas/<token>`) uses `[canvas.viewportBounds]` (`minX`, `minY`, `maxX`, `maxY`, canvas px) when present, else fits all nodes. So:

- Omit both tables for a new canvas; the workbench writes them when a user pans.
- To control how a *shared* canvas opens, set `viewportBounds` to the rectangle you want framed (for example the bounding box of the first row). Never hand-write `viewport` zoom math.
