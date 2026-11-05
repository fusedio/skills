---
name: html-template-nodes
description: Authoring reference for Fused canvas HTML template nodes, the `.html` file in a canvas folder that renders as a sandboxed iframe with `window.fused` (`fused.params`, `fused.runPython`, `fused.query`) and `$param` / `{{udf}}` substitution. Use when creating, editing, debugging, wiring, or sharing an HTML node, when a page needs to read canvas params, call a canvas UDF or run SQL over a map layer from JavaScript, when a page should embed a JSON-UI widget (`<fused-widget>`), when custom charts should cross-filter with a fused-map, or when deciding between an HTML node, the JSON-UI `html` widget, the `iframe` widget, and a Python UDF that returns HTML.
---

# Fused canvas HTML template nodes

> **CLI version:** commands below are written `fused workbench …` (only the 2.9.2b0+ pre-releases have this namespace; released versions such as 2.9.1 and 2.9.3 don't). If `fused workbench` fails with `No such command 'workbench'`, drop the word `workbench` — e.g. `fused canvas push`. See `fused-workbench-cli`.

An HTML template node is a canvas node whose source is a plain `.html` file. The workbench renders it client-side in a sandboxed iframe, injects a `window.fused` bridge, and substitutes `$param` / `{{udf}}` placeholders in the markup. It never executes on the backend: all data comes from the Python UDFs it is wired to.

Read this whole file before writing an HTML node. The runtime contract below is copied from the client source (`core/fused-bridge-script.ts`, `hooks/use-fused-bridge.ts`, `json-ui/inline-substitution.ts`); when the workbench UI and this file disagree, the UI wins — report the drift.

## Files and `canvas.toml`

```
my_canvas/
  canvas.toml
  load_data.py        # Python UDF the page reads from
  dashboard.html      # HTML template node — stem = udfName
```

- The node type is inferred from the `.html` extension. The `[[canvas.nodes]]` entry is a normal node (`udfName`, `x`, `y`, `zIndex`, `width`, `height`, optional `title` / `description` / `visible`). There is no `type` key for HTML nodes and no HTML-specific fields.
- The file content is stored verbatim as the node source. Do not wrap it in Python, do not paste a runtime, do not add `<script src="./x.js">` (there is no sibling directory — inline everything, or use an absolute CDN URL).
- Stems must be unique in the folder (`dashboard.html` and `dashboard.py` cannot coexist).
- Every UDF the page reads from needs an **explicit edge into the HTML node** in `canvas.toml`. See [Edges](#edges).

```toml
[canvas]
edges = [
  ["load_data", "dashboard"],   # dashboard reads load_data via {{load_data}} or fused.runPython("load_data")
]

[[canvas.nodes]]
udfName = "load_data"
visible = true                  # required if dashboard uses bare {{load_data}}
x = 0
y = 0
zIndex = 1
width = 700
height = 500

[[canvas.nodes]]
udfName = "dashboard"
title = "Dashboard"
x = 775                         # 0 + 700 + 75 (see canvas-toml "Layout rules")
y = 0
zIndex = 2
width = 900
height = 600
```

## Two ways to get data into the page

| Mechanism | When it resolves | Reloads the page? | Use for |
|---|---|---|---|
| `$param` / `{{udf}}` substitution in the markup | Host rewrites the HTML string before loading the iframe | **Yes** — every change to a referenced param or UDF result reloads the iframe; page state, timers and in-flight `runPython` calls are lost | Values fixed for the life of the page: titles, one-off embeds of a UDF's HTML output, a static table |
| `fused.params` + `fused.runPython` in `<script>` | At runtime, from JavaScript | No | Anything interactive |

**Never reference the same param both as `$x` in markup and via `fused.params` in script.** Each change of `x` would reload the page and discard the script's work.

## Substitution grammar (markup)

Applied to the HTML string before the iframe loads: to the whole source, `<script>` included, except the text inside `<fused-widget>` elements. A `{{name}}` or `$name` written literally in a script string is rewritten too, so build such strings at runtime (`"{".repeat(2) + "listings" + "}".repeat(2)`, `"$" + "p_min"`).

### `$name` — canvas param

- Matches `$` followed by an identifier: `[A-Za-z_][A-Za-z0-9_]*`. **Only the bare form.** `${name}` is not substituted in the page and `$$` is not an escape (the second `$` still starts a match). Verified: with `title=Hello`, `$title` → `Hello`, `${title}` → `${title}`, `$$title` → `$Hello`. Use bare `$name` only; to print a literal dollar before a param-looking word, emit it from script.
- Stringified: strings as-is, numbers/booleans via `String()`, objects/arrays as JSON, `null` → empty string.
- Missing (unset or not visible through edges) params **stay literal** in the page.
- Every `$name` in the file also becomes a `str` parameter of the node (shown in its parameter panel, hydratable from a share URL). This scan does treat `${name}` as a param and `$$` as an escape, so a JS template literal `${x}` shows up as a bogus node param `x` even though it is not substituted.
- The regex has no awareness of `<script>`. A JavaScript identifier like `$el` or `$scope` is a param reference: if a connected node broadcasts a param with that name it gets replaced inside your code. Avoid `$`-prefixed identifiers in page JS, or name them so they cannot collide.

### `{{udf}}` — inline a connected UDF's result

- `{{udf_name}}` — the UDF's cached result, stringified:
  - UDF returned HTML (a `str`): the raw HTML, inlined verbatim.
  - UDF returned a DataFrame: a **columnar** JSON object, `{"col_a": [..], "col_b": [..]}` (up to 10,000 rows).
  - Anything else: `JSON.stringify` of the value.
- `{{udf_name.column}}` — one column as a JSON array. `{{udf_name.column[0]}}` — one cell as a plain scalar string. Column and index may be params: `{{udf_name.$col[$row]}}`. Selecting a column on an HTML-returning UDF yields an empty string and a warning in the widget log.
- `{{udf_name?k=v&k2=$param}}` — run the UDF **live** with override params (merged over the UDF's own panel values), instead of reading its cached result. Result stringified as above; `{{udf?k=v}}` can be combined with `.column[0]`. Observed on a public share page: the override form rendered empty while `fused.runPython` with the same params succeeded — for parameterized data prefer `runPython` in script, and check the override form on the canvas before relying on it in a shared page.
- Whitespace inside the braces is tolerated (`{{ udf_name }}`).
- Not connected by an edge → empty string, silently. Connected but no cached result yet → the placeholder renders as the text `Loading...` until the source finishes; the rest of the page renders normally. A **hidden source (`visible = false`) never auto-runs, so a bare `{{udf}}` on it shows `Loading...` forever.** Only the bare form needs a cached result; `{{udf?k=v}}` and `fused.runPython` run on demand and work on hidden sources.
- `$` characters inside inlined UDF output are not re-substituted.
- `{{other_html_node}}` inlines another HTML template node (its `$name`, `${name}` and `$$` resolved from the override params, then its own `{{udf}}` refs resolved through *its* edges). Max nesting depth 8.

## Runtime: `window.fused`

Injected by the host at render time. Never define `window.fused` yourself; never reference `fusedCanvas` (removed).

| Member | Contract |
|---|---|
| `fused.env` | Always `"workbench"` — on the canvas **and** on share pages. |
| `fused.device` | `"desktop"`. |
| `fused.params.get(name)` | Current value of a canvas param visible to this node. Any JSON value (string, number, boolean, object such as a viewport or range). `undefined` when unset or not visible. Synchronous and correct from the first line of page script. |
| `fused.params.getAll()` | Plain-object copy of every visible param. |
| `fused.params.set(name, value)` | Broadcast to connected nodes with this node as origin. `set(name, null)` clears. `set({ a: 1, b: "x" })` sets several. Any JSON value; throws on empty key or function value. Fires your own `onChange`. |
| `fused.params.onChange(cb)` | `cb(allParams)` after any visible param changes, own `set` included. Returns an unsubscribe function. No-op updates do not fire. |
| `await fused.runPython(udfName, params?, opts?)` | Runs a connected canvas UDF **by node name** (not a path, not `user/name`). Resolves with the parsed JSON body: DataFrame → **array of row objects**; non-JSON output → text. Rejects with an `Error` carrying `.type` and `.message`. |
| `await fused.query(sql, opts?)` | Runs one DuckDB query in the viewer's browser over `{{name}}` sources and resolves with an **array of row objects**. A source is a `fused-map` layer id, a `sql-runner` name, or a connected UDF. Rejects with an `Error` carrying `.type` and `.message`. See [`fused.query` details](#fusedquery-details). |
| Not available | `readFile`, `writeFile`, `stat`, `rawUrl`, `ai`, `fileIndex`, `capture`, `trackJob`, `daemon`. These members are simply absent (`typeof fused.readFile === "undefined"`), so calling them throws a `TypeError`. Anything needing files or Python goes in a UDF; call it with `runPython`. |

### `fused.runPython` details

- `params` values are sent as strings (non-strings JSON-encoded). Annotate the UDF's parameters (`n: int`, `bbox: list`, `flag: bool`) so they coerce; unannotated numeric params arrive as strings.
- Your params merge over the UDF's own panel values (yours win, the panel fills the gaps) — same as `{{udf?k=v}}`.
- **Stale-cancel by default, keyed per `udfName`**: a newer call supersedes the in-flight one and the superseded promise **never settles**. `opts.key` regroups (`{ key: "chart-a" }`), `opts.key: null` allows full concurrency, `opts.signal` is your own `AbortSignal` (rejects with `.type === "aborted"`).
- Error types: `not_allowed` (no edge from a node with that name into this node — this is also what a misspelled or non-existent name produces, since the edge check runs first), `not_found` (edge exists but the node is gone), `no_environment` (workbench has no active execution environment yet), `invalid_args`, `udf_error` (the UDF raised; `.message` has the error text), `aborted`.
- Always `try/catch` and render the error into the page. Uncaught rejections are silent — there is no traceback overlay in the workbench.
- On the canvas the call runs the **live** node code through the authenticated realtime path. On a share page it runs through the canvas share token (no execution environment needed).
- When a connected source UDF finishes a new run, the host **reloads the iframe** so `runPython` calls refetch. Design `draw()` to be re-runnable from scratch. The node toolbar's "Invalidate cache" / run button also just reloads the iframe.

### `fused.query` details

`fused.query("SELECT … FROM {{name}} …", { params, maxRows, key, signal })`

Needs a workbench that includes fusedlabs/application#8469 (unstable on 2026-11-05). Check before building on it: `typeof fused.query === "function"` in the page.

- **Sources.** Each `{{name}}` in the SQL resolves to, in this order:
  1. a `fused-map` layer whose `id` is `name`, or a `sql-runner` whose `name` is `name`, when it is in reach: inside this page (a `<fused-widget>` map), or on a node with an edge into this node, or drawn from a UDF with an edge into this node;
  2. else the cached result of a UDF named `name` with an edge into this node.
- **Build the SQL string at runtime** (see [Substitution grammar](#substitution-grammar-markup)). A literal `"{{listings}}"` in script arrives as `""`; a literal `"$p_min"` arrives as the param's value once `p_min` is set, and the page reloads on every change of it.
- **`opts.params`** is an object that fills every `$name` in the SQL. A `$name` with no entry rejects `invalid_args` (`$x has no value; pass it in params`). Values render like this:

  | Value | Renders as | Use with |
  |---|---|---|
  | number | `100` | `price > $min` |
  | string | `'it''s'` (quoted, `'` doubled) | `room_type = $t` |
  | `null` | `''` | avoid: leave the clause out instead |
  | `undefined` (an unset `fused.params` value) | dropped in transit: the call rejects `invalid_args` | leave the clause out |
  | array | `('Hotel room', 'Shared room')` | `room_type IN $types` (`IN ($types)` works too) |
  | empty array `[]` | `(NULL)`, matches **no** rows | leave the clause out when the list is empty |
  | `{ min, max }` | `100 AND 200`; a missing or `null` bound becomes `-1e308` / `1e308` | `price BETWEEN $range` on a numeric column |
  | anything inside a quoted SQL string | its raw text | `'prefix_$name'` |

- **`opts.maxRows`** appends `LIMIT n` unless the SQL has its own `LIMIT`. There is no cap by default: `SELECT id FROM {{listings}}` returned all 5,765 rows. Aggregate in SQL (`GROUP BY`, `COUNT(*)`) rather than pulling raw rows into the page.
- **Result.** An array of row objects. `COUNT(*)` and other BIGINT values arrive as numbers.
- **Stale-cancel is keyed by the SQL text plus the options.** Repeating the exact same call while one is in flight supersedes it and the older promise never settles. A call with different SQL or different params does **not** cancel the older one: both settle, in any order. When a redraw changes the filters, drop late results with a generation counter (see [Wiring pattern](#wiring-pattern)) or give each chart its own `opts.key` (a newer call with that key supersedes the older). Never share one key among calls you await together: the superseded call never settles, so `Promise.all` never resolves. `opts.signal` aborts: the promise rejects with `.type === "aborted"`.
- **Errors** (`e.type`):

  | `.type` | When |
  |---|---|
  | `not_allowed` | `name` is neither a source in reach nor a UDF with an edge into this node. A misspelled name lands here too, and so does a `{{layer_id}}` queried right after page load, before the map in the page has mounted. Message: `UDF 'name' is not connected to this node. Add an edge from it to this node.` |
  | `not_ready` | The layer has no rows yet (its UDF is still running) or the UDF is still running. Retry after a short wait. |
  | `query_error` | DuckDB rejected the SQL (syntax, unknown column). `.message` is DuckDB's text. |
  | `invalid_args` | A `$name` has no value in `params`, `params` is not an object, or the SQL uses `{{udf?k=v}}` (not supported: run the UDF with `fused.runPython`). |
  | `not_found` | There is an edge, but nothing on the canvas publishes or runs under that name. Unknown names usually reject `not_allowed` first. |
  | `aborted` | Your `opts.signal` aborted. |

  An empty or non-string `sql` rejects with a plain `Error` that has no `.type`.
- Every call is written to the node's runtime log: `fused.query started: <sql>`, then `completed: N rows in Ms` or `failed (<type>, Ms): <message>`.
- The query runs in the viewer's browser. Querying a layer does not run its UDF again.

## Edges

Visibility follows canvas edges. This node sees params from, and may `runPython` against, **only UDF nodes with an edge into it** (bidirectional edges count both ways).

- No edge → `runPython` and `fused.query` reject `not_allowed`, `params.get` is `undefined`, `{{udf}}` renders empty.
- `fused.params.set` travels out along edges the same way: a downstream UDF with that parameter re-runs, a widget with `$x` re-substitutes, another HTML node receives `onChange`.
- In `canvas.toml` edges are always explicit: `["source_udf", "html_node"]`. Add one per UDF referenced via `{{udf}}` or `fused.runPython("udf")`, and `["html_node", "target_udf"]` for each UDF the page drives with `fused.params.set`.
- In the workbench UI, edges are also inferred from `{{udf}}` placeholders and from literal `fused.runPython("udf_name")` calls. Names built with template literals (`` fused.runPython(`${x}`) ``) or variables are **not** detected — write the literal name, or add the edge by hand.
- If the request needs data from a node that is not connected, say so and add the edge; do not work around it.

## Wiring pattern

Params ARE state. Controls write params only; `onChange` is the single re-render path; `draw()` reads params, never the control. Any other node on the same edges then reproduces the view from params alone, and a share URL (`?city=x&limit=5`) hydrates the same state.

```html
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<style>
  :root { --bg: #111; --fg: #eee; --accent: #E8FF59; }
  body { margin: 0; padding: 16px; font: 14px system-ui, sans-serif; background: var(--bg); color: var(--fg); }
  #out { margin-top: 12px; white-space: pre-wrap; }
</style>
</head>
<body>
  <label>City <select id="city"><option value="">—</option><option>Paris</option><option>Tokyo</option></select></label>
  <label>Limit <input id="limit" type="range" min="1" max="50" value="10" /></label>
  <div id="out">Pick a city</div>

<script>
  const city = document.getElementById("city");
  const limit = document.getElementById("limit");
  const out = document.getElementById("out");

  // controls -> params
  city.addEventListener("change", () => fused.params.set("city", city.value || null));
  let t;
  limit.addEventListener("input", () => {
    clearTimeout(t);
    t = setTimeout(() => fused.params.set("limit", Number(limit.value)), 150);
  });

  // params -> view
  let gen = 0;
  async function draw(p) {
    const my = ++gen;            // every draw invalidates older ones
    city.value = p.city ?? "";
    limit.value = String(p.limit ?? 10);
    if (!p.city) { out.textContent = "Pick a city"; return; }
    out.textContent = "Loading…";
    try {
      const rows = await fused.runPython("city_stats", { city: p.city, limit: Number(p.limit ?? 10) });
      if (my !== gen) return;    // a newer draw() ran meanwhile (e.g. city cleared)
      out.textContent = rows.map(r => `${r.name}: ${r.value}`).join("\n");
    } catch (e) {
      if (e.type === "aborted" || my !== gen) return;
      out.textContent = `${e.type}: ${e.message}`;
    }
  }

  fused.params.onChange(draw);
  draw(fused.params.getAll());
</script>
</body>
</html>
```

Rules the example follows:

- Debounce sliders and drags (~150 ms). Stale-cancel keeps only the newest result but every tick still costs a request.
- Stale-cancel only fires when a *later* `runPython` (or identical `fused.query`) uses the same key. A `draw()` that returns early without calling `runPython` (empty selection, validation failure) does not cancel the previous fetch, which would then overwrite the cleared view. Guard with a generation counter as in the example, or hold an `AbortController` per view and abort it at the top of `draw()`.
- Coerce in `draw()` (`Number(p.limit)`): params set by another node or hydrated from a share URL may arrive as strings, numbers or JSON depending on origin.
- Before writing rendering code for an unknown result shape, `console.log` the first `runPython` result (open the browser devtools on the canvas) — do not invent column names.
- Keep data preparation in Python UDFs; the page renders and coordinates UI behaviour.

## Embedding widgets with `<fused-widget>`

A JSON-UI widget can be placed inside the page. Write its spec as the text of a `<fused-widget>` element; the workbench renders the widget over that element's box.

```html
<fused-widget style="display:block;height:64px">
  { "type": "dropdown",
    "props": { "label": "City", "param": "city",
               "sql": "SELECT DISTINCT city AS value, city AS label FROM {{rain}} ORDER BY 1" } }
</fused-widget>

<fused-widget style="display:block;height:260px">
  { "type": "bar-chart",
    "props": { "sql": "SELECT month AS label, mm AS value FROM {{rain}} WHERE city = $city ORDER BY 1" } }
</fused-widget>
```

- **Text is the spec.** Same schema as a `.json` widget file (`type`, `props`, optional `children`), parsed as JSON5. See `json-ui-schemas`.
- **The element is the box.** Size it with CSS; `height` at least. The widget fills it. There is no auto-sizing.
- **Same wiring as a widget node.** `{{udf}}` and `$param` inside the spec belong to the widget and resolve live through the HTML node's edges; the page-level substitution pass skips `<fused-widget>` blocks, so they never reload the iframe. A `{{udf}}` inside the spec still needs the edge `["udf", "html_node"]` in `canvas.toml` (the UI infers it from the source as usual).
- **Inputs set params with the HTML node as origin.** A dropdown inside the element that sets `city` is indistinguishable from the page calling `fused.params.set("city", …)`: the page's `onChange` fires and downstream UDFs re-run.
- **Read once; lifetime follows the DOM.** The spec is read when the element connects. To change it, replace the element. Removing the element removes the widget. Every iframe reload (substitution change, upstream run, Run button) drops widgets and the page re-registers them on load.
- **Errors in place.** A spec that fails to parse or validate shows the workbench's standard error card inside the element.
- **Sidebar edits write into the block.** A `fused-map` inside the element is editable from its sidebar on your own canvas (Add layer, basemap, layer styles, filters): each edit is written into that `<fused-widget>` block of the `.html` file, one undo step in the code editor, exactly as it would be for a `.json` widget node. The rest of the page is untouched. On a share page the edits are runtime overrides, as for any widget.
- **Only authored elements render.** The workbench renders the specs it finds in the node's source file. An element the page creates at runtime from other text (for example by echoing a param) renders nothing. Elements inside a template inlined through `{{other_html_node}}` are not rendered either; put the widget in the outer page.
- **Write the spec raw.** The text between the tags is parsed as is: write `<`, `>` and `&` directly, not as HTML entities.
- **Talk to the widget through params and SQL.** The page cannot call methods on the widget. Send it values with `fused.params.set` (read by a `$param` in the spec, or by a map filter bound to `$param`), read what it sets (`param`, a map's `selectParam`) with `fused.params.get` / `onChange`, and read a `fused-map`'s layer rows with `fused.query` (`{{layer_id}}`). See [Cross-filtering](#cross-filtering-a-map-with-custom-charts).
- **Painted above the page.** The widget uses the workbench theme and sits above the page's own content: page modals, tooltips and sticky headers cannot cover it. Hide or remove the element while a page modal is open.
- Works the same on the canvas, on the share page (`/share/<token>/<html_node>`, where `$param` in the spec hydrates from the URL like any node param) and inside fused-render's embedded workbench.

## Cross-filtering a map with custom charts

A cross-filter view is a map plus charts where a choice in any one of them filters all the others. Build it as **one HTML node**: a `fused-map` inside `<fused-widget>`, plus charts and controls the page draws itself. A complete, tested example is in [`examples/crossfilter/`](examples/crossfilter/) next to this file. The template below is the same code. It needs a workbench with `fused.query`, `$param` filters and `selectParam` (fusedlabs/application#8451 and #8469; unstable on 2026-11-05).

How it works, in plain words:

1. **Every filter is a canvas param.** This is the [Wiring pattern](#wiring-pattern) with `fused.query` in place of `runPython`: controls and charts only call `fused.params.set`, and `fused.params.onChange(draw)` redraws everything. The map's box select writes the `selected` param.
2. **The map filters itself.** Its layer `filters` name the same params (`"min": "$p_min"`). When a param changes, the map hides the points that fail, in the browser.
3. **The charts ask SQL.** Each chart calls `fused.query` over the map's layer (`{{listings}}`, the layer `id`) and adds the active filters as a `WHERE` clause. `{{listings}}` holds every row of the UDF's result, filtered or not, so the page must apply the filters itself.
4. **Each chart ignores its own filter.** The price histogram applies the room-type and map-box filters but not the price range, so every bar stays visible and the brushed range is drawn highlighted. The room-type chart does the same for room types.

### Names that must match

Rename these consistently when you adapt the template. Every row lists all the places that name appears.

| Name in the template | What it is | Appears in |
|---|---|---|
| `airbnb_listings` | data UDF node | file `airbnb_listings.py`; `udfName` and the edge `["airbnb_listings", "crossfilter"]` in `canvas.toml`; `"udf": "{{airbnb_listings}}"` in the map spec |
| `crossfilter` | HTML node | file `crossfilter.html`; `udfName` and both edges in `canvas.toml` |
| `listings` | map layer `id` | `"id": "listings"` in the map spec; `SOURCE` in the script; `{{listings}}` in any JSON-UI widget that charts the layer |
| `id`, `price`, `room_type`, `lat`, `lng` | columns the UDF returns | filter `attr`s, `selectKey`, `latColumn` / `lngColumn`, `tooltip` in the map spec; every SQL string in the script |
| `p_min`, `p_max` | price range params | `"min": "$p_min"`, `"max": "$p_max"` in the map spec; in the script: `read()`, the input ids, the brush and the Clear button |
| `room_types` | category list param | `"values": "$room_types"` in the map spec; in the script: `read()`, the room bars' `fused.params.set` and the Clear button |
| `selected` | map selection param | `"selectParam": "selected"` in the map spec; in the script: `read()` and the Clear button |

Param values the template relies on:

| Param | Value | Unset (`undefined`) means |
|---|---|---|
| `p_min`, `p_max` | number | no bound on that side; the map ignores it and the page leaves it out of the SQL |
| `room_types` | array of strings | no category filter. Treat `[]` the same (the map sidebar writes `[]` when every category is unchecked); clear with `null` yourself (see [Mistakes](#mistakes-and-their-symptoms)). |
| `selected` | `{ layer, key, ids, count, bbox, mode, truncated }`, set by the map | no selection. After Escape or a plain click it is `{ mode: "none", ids: [], bbox: null, … }`, not `undefined`: test `bbox` and `ids.length`, not the object. |

### Recipe

1. **Write the data UDF** (`airbnb_listings.py`). Return one row per point: an integer `id`, `lat` and `lng` as numbers, and the columns you filter on. Return the whole table; the map loads it once.
2. **Write the HTML node** (`crossfilter.html`). Copy the template. Rename per [Names that must match](#names-that-must-match): the layer `id` and `SOURCE` must be the same word, and every `$param` in the map spec must be a name the script sets.
3. **Add the edges** in `canvas.toml`: `["<data_udf>", "<html_node>"]`, as for any UDF the page reads (the workbench UI infers it from the spec too). For a JSON-UI widget on another node that reads `{{<layer_id>}}`, also add `["<html_node>", "<widget_node>"]` and `[validate] skip = ["widget_refs"]` (validate does not know layer ids). Without such a widget, leave out `room_chart.json`, its node, its edge and the `[validate]` block.
4. **Validate and push.**
   ```sh
   fused workbench canvas validate ./my_canvas
   fused workbench canvas push ./my_canvas --canvas my_canvas
   ```
   Validate does not read `.html` files: check the `{{name}}` refs by hand as in [Debug and verify](#debug-and-verify-with-the-cli). To check the map spec, save the text inside `<fused-widget>` as a `.json` file and run `fused workbench --env <env> json-ui validate <file>` with the deployment you push to (see `json-ui-schemas`, section on `fused-map` filters).
5. **Check it works.** Open the canvas and confirm each line:
   - the map shows points, the histogram and the room bars draw, the status line shows the row count;
   - dragging across the histogram thins the map and changes the room bars, while the histogram keeps all its bars;
   - clicking a room bar thins the map and changes the histogram, while the room chart keeps all its bars;
   - shift+drag on the map draws a box and both charts count only the points inside it;
   - Escape clears the box; **Clear all filters** restores everything.

   The node's log panel shows each `fused.query` with its row count or error.

### Template

`canvas.toml`:

```toml
type = "canvas"
version = 2
name = "Cross-filter example"

[validate]
skip = ["widget_refs"]

[canvas]
edges = [
  ["airbnb_listings", "crossfilter"],
  ["crossfilter", "room_chart"],
]

[[canvas.nodes]]
udfName = "airbnb_listings"
title = "Airbnb listings"
visible = true
x = 0
y = 0
zIndex = 1
width = 700
height = 500

[[canvas.nodes]]
udfName = "crossfilter"
title = "Cross-filter"
visible = true
x = 775
y = 0
zIndex = 2
width = 1300
height = 760

[[canvas.nodes]]
udfName = "room_chart"
title = "Room chart"
visible = true
x = 2150
y = 0
zIndex = 3
width = 600
height = 400
```

`airbnb_listings.py`:

```python
@fused.udf
def udf(path: str = "s3://fused-sample/demo_data/airbnb_listings_sf.parquet"):
    import pandas as pd

    df = pd.read_parquet(
        path,
        columns=["name", "room_type", "price_in_dollar", "latitude", "longitude"],
    )
    df = df.dropna(subset=["price_in_dollar", "latitude", "longitude"])
    df = df.rename(columns={"price_in_dollar": "price", "latitude": "lat", "longitude": "lng"})
    df.insert(0, "id", range(len(df)))
    return df.reset_index(drop=True)
```

`crossfilter.html`:

```html
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<style>
  :root { --bg: #111; --fg: #eee; --muted: #8a8a8a; --dim: #3a3a3a; --accent: #E8FF59; }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 12px; font: 13px system-ui, sans-serif; background: var(--bg); color: var(--fg); }
  .layout { display: grid; grid-template-columns: 1fr 380px; gap: 16px; height: calc(100vh - 24px); }
  .map { height: 100%; }
  .panel { display: flex; flex-direction: column; gap: 16px; overflow: auto; }
  h3 { margin: 0 0 6px; font-size: 13px; }
  small { color: var(--muted); font-weight: normal; }
  input, button { background: #222; color: var(--fg); border: 1px solid var(--dim); }
  input { width: 90px; padding: 4px; }
  button { padding: 6px 10px; cursor: pointer; }
  #hist { display: block; width: 100%; height: 150px; cursor: crosshair; user-select: none; }
  .room { display: grid; grid-template-columns: 130px 1fr 50px; gap: 8px; align-items: center; padding: 3px 0; cursor: pointer; }
  .room .bar { height: 14px; background: var(--accent); }
  .room.off .bar { background: var(--dim); }
  .room .n { text-align: right; color: var(--muted); }
</style>
</head>
<body>
<div class="layout">
  <fused-widget class="map">
    {
      "type": "fused-map",
      "props": {
        "style": "height:100%",
        "centerLng": -122.44, "centerLat": 37.76, "zoom": 11.5,
        "selectParam": "selected",
        "selectKey": "id",
        "layers": [{
          "id": "listings",
          "type": "scatterplot",
          "udf": "{{airbnb_listings}}",
          "latColumn": "lat", "lngColumn": "lng",
          "filters": [
            { "attr": "price", "type": "range", "min": "$p_min", "max": "$p_max" },
            { "attr": "room_type", "type": "categories", "values": "$room_types" }
          ],
          "tooltip": ["name", "room_type", "price"],
          "style": { "fillColor": [232, 255, 89], "pointRadius": 3 }
        }]
      }
    }
  </fused-widget>
  <div class="panel">
    <div>
      <h3>Price</h3>
      <label>Min <input id="p_min" type="number" step="10" /></label>
      <label>Max <input id="p_max" type="number" step="10" /></label>
    </div>
    <div>
      <h3>Price histogram <small>drag to filter, click to clear</small></h3>
      <svg id="hist"></svg>
    </div>
    <div>
      <h3>Room type <small>click to filter</small></h3>
      <div id="rooms"></div>
    </div>
    <div><span id="status">Loading…</span> <small>Shift+drag on the map to select an area, Escape to clear it.</small></div>
    <div><button id="clear">Clear all filters</button></div>
  </div>
</div>

<script>
  const SOURCE = "{".repeat(2) + "listings" + "}".repeat(2);
  const P = "$";
  const BIN = 50;
  const LAST_BIN = 20;
  const BINS = LAST_BIN + 1;
  const label = (b) => (b === LAST_BIN ? BIN * LAST_BIN + "+" : String(b * BIN));

  const byId = (id) => document.getElementById(id);
  const hist = byId("hist");
  const rooms = byId("rooms");
  const status = byId("status");
  const inputs = [byId("p_min"), byId("p_max")];

  const num = (v) => (v === null || v === undefined || v === "" || isNaN(Number(v)) ? null : Number(v));
  const list = (v) => (Array.isArray(v) ? v : typeof v === "string" ? v.split(",").map((t) => t.trim()).filter(Boolean) : []);
  const read = (p) => ({ lo: num(p.p_min), hi: num(p.p_max), types: list(p.room_types), sel: p.selected });

  function filters(f, skip) {
    const where = [];
    const params = {};
    const add = (sql, name, value) => { where.push(sql + " " + P + name); params[name] = value; };
    if (skip !== "price" && (f.lo !== null || f.hi !== null)) add("price BETWEEN", "price", { min: f.lo, max: f.hi });
    if (skip !== "room_type" && f.types.length) add("room_type IN", "room_types", f.types);
    if (f.sel?.bbox) {
      add("lng BETWEEN", "box_lng", { min: f.sel.bbox[0], max: f.sel.bbox[2] });
      add("lat BETWEEN", "box_lat", { min: f.sel.bbox[1], max: f.sel.bbox[3] });
    } else if (f.sel?.ids?.length) {
      add("id IN", "ids", f.sel.ids);
    }
    return { where: where.length ? " WHERE " + where.join(" AND ") : "", params };
  }

  function query(select, f, skip, rest = "") {
    const w = filters(f, skip);
    return fused.query("SELECT " + select + " FROM " + SOURCE + w.where + " " + rest, { params: w.params });
  }

  let gen = 0;
  async function draw(p, tries = 0) {
    const my = ++gen;
    const f = read(p);
    for (const input of inputs) {
      if (document.activeElement !== input) input.value = num(p[input.id]) ?? "";
    }
    try {
      const [bins, types, total] = await Promise.all([
        query("LEAST(FLOOR(price / " + BIN + "), " + LAST_BIN + ") AS bin, COUNT(*) AS n", f, "price", "GROUP BY 1 ORDER BY 1"),
        query("room_type, COUNT(*) AS n", f, "room_type", "GROUP BY 1 ORDER BY 2 DESC"),
        query("COUNT(*) AS n", f),
      ]);
      if (my !== gen) return;
      drawHistogram(bins, f);
      drawRooms(types, f);
      let scope = "";
      if (f.sel?.mode === "box") scope = " inside the map box";
      if (f.sel?.mode === "click") scope = " among " + f.sel.count + " clicked";
      status.textContent = total[0].n.toLocaleString() + " listings match" + scope + ".";
    } catch (e) {
      if (my !== gen) return;
      if (e.type === "not_ready" || (e.type === "not_allowed" && tries < 20)) {
        setTimeout(() => my === gen && draw(fused.params.getAll(), tries + 1), 500);
        return;
      }
      status.textContent = e.type + ": " + e.message;
    }
  }

  const binWidth = () => hist.clientWidth / BINS;

  function drawHistogram(rows, f) {
    const plotH = hist.clientHeight - 16;
    const max = Math.max(1, ...rows.map((r) => r.n));
    const on = (b) => (f.lo === null || b * BIN >= f.lo) && (f.hi === null || b * BIN < f.hi);
    let svg = "";
    for (const r of rows) {
      const bh = (r.n / max) * (plotH - 2);
      const fill = on(r.bin) ? "var(--accent)" : "var(--dim)";
      svg += '<rect x="' + (r.bin * binWidth() + 1) + '" y="' + (plotH - bh) + '" width="' + (binWidth() - 2) + '" height="' + bh + '" fill="' + fill + '"><title>' + label(r.bin) + ": " + r.n + "</title></rect>";
    }
    for (let b = 0; b <= LAST_BIN; b += 5) {
      const end = b === LAST_BIN;
      svg += '<text x="' + (end ? hist.clientWidth : b * binWidth()) + '" y="' + (plotH + 13) + '" text-anchor="' + (end ? "end" : "start") + '" fill="var(--muted)" font-size="10">' + label(b) + "</text>";
    }
    hist.innerHTML = svg + '<rect id="brush" y="0" height="' + plotH + '" width="0" fill="white" fill-opacity="0.15"></rect>';
  }

  const binAt = (x) => Math.max(0, Math.min(LAST_BIN, Math.floor(x / binWidth())));
  const xOf = (e) => e.clientX - hist.getBoundingClientRect().left;
  let dragFrom = null;
  hist.addEventListener("mousedown", (e) => { dragFrom = xOf(e); });
  hist.addEventListener("mousemove", (e) => {
    if (dragFrom === null) return;
    const x = xOf(e);
    const brush = byId("brush");
    brush.setAttribute("x", Math.min(dragFrom, x));
    brush.setAttribute("width", Math.abs(x - dragFrom));
  });
  window.addEventListener("mouseup", (e) => {
    if (dragFrom === null) return;
    const x0 = dragFrom;
    const x1 = xOf(e);
    dragFrom = null;
    if (Math.abs(x1 - x0) < 4) {
      fused.params.set({ p_min: null, p_max: null });
      return;
    }
    const a = binAt(Math.min(x0, x1));
    const b = binAt(Math.max(x0, x1));
    fused.params.set({ p_min: a * BIN, p_max: b === LAST_BIN ? null : (b + 1) * BIN - 0.01 });
  });

  function drawRooms(rows, f) {
    const max = Math.max(1, ...rows.map((r) => r.n));
    rooms.innerHTML = "";
    for (const r of rows) {
      const row = document.createElement("div");
      row.className = "room" + (f.types.length && !f.types.includes(r.room_type) ? " off" : "");
      row.innerHTML = "<span></span><div class=\"bar\" style=\"width:" + (100 * r.n / max) + "%\"></div><span class=\"n\">" + r.n + "</span>";
      row.querySelector("span").textContent = r.room_type;
      row.addEventListener("click", () => {
        const now = list(fused.params.get("room_types"));
        const next = now.includes(r.room_type) ? now.filter((t) => t !== r.room_type) : [...now, r.room_type];
        fused.params.set("room_types", next.length ? next : null);
      });
      rooms.appendChild(row);
    }
  }

  for (const input of inputs) {
    input.addEventListener("change", () => fused.params.set(input.id, num(input.value)));
  }
  byId("clear").addEventListener("click", () => {
    fused.params.set({ p_min: null, p_max: null, room_types: null, selected: null });
  });

  fused.params.onChange(draw);
  draw(fused.params.getAll());
</script>
</body>
</html>
```

What each part of the script does:

- `read(p)` turns the params into plain values once per draw.
- `filters(f, skip)` builds the `WHERE` clause and `opts.params`, one `add()` per active filter, leaving out the filter named by `skip`. A map box filters by `bbox` (`[west, south, east, north]`); a shift+click selection has `bbox: null` and filters by `id IN $ids`.
- `draw(p)` runs the three queries together and drops stale results with `gen`. It retries every 500 ms: on `not_ready` until the layer has rows, on `not_allowed` for 10 s, because the map publishes its layer a moment after the page loads.
- The brush sets `p_max` to just below the next bin (`249.99`), because both the map filter and SQL `BETWEEN` include the upper bound.

Optional: a plain JSON-UI chart on another node can read the same layer. `room_chart.json`, with the edge `["crossfilter", "room_chart"]`:

```json
{
  "type": "bar-chart",
  "props": {
    "title": "Listings per room type",
    "sql": "SELECT room_type AS label, COUNT(*) AS value FROM {{listings}} GROUP BY 1 ORDER BY 2 DESC",
    "rotateLabels": false
  }
}
```

It shows every row of the layer and does not follow the filters. A `{{layer_id}}` source only exists while its map is on the page. On the canvas the chart reads it. Opened alone at `/share/<token>/room_chart`, it shows `UDF 'listings' is not connected via an edge`.

### Mistakes and their symptoms

| Symptom | Cause | Fix |
|---|---|---|
| Charts show `query_error: Parser Error: syntax error at or near "WHERE"` (or `"GROUP"`, or `at end of input`) | `"{{listings}}"` written literally in the script; the host replaced it with an empty string | Build it at runtime: `"{".repeat(2) + "listings" + "}".repeat(2)` |
| The page flashes and loses its state on every filter change | `$p_min` (or any `$param`) written literally in the page outside `<fused-widget>`; the host substitutes it and reloads the page | Build `$` at runtime (`const P = "$"`); pass values in `opts.params` |
| `not_allowed: UDF 'listings' is not connected to this node` that does not go away | The name in `{{…}}` is not the layer `id` (a map inside the page is always in reach) | Make `SOURCE` and the layer `id` the same word |
| Charts stay on `not_allowed` or `not_ready` after a fresh load | No retry; the map publishes its layer only after it has mounted and loaded the UDF | Retry those two types for a while, as `draw` does |
| A row on a bin edge (price exactly 250) is counted in the brushed range | The brush's upper bound equals the next bin's start; map filters and `BETWEEN` include it | Stop just below the next bin, as the template does |
| A chart's bars vanish when you click one, so you cannot pick another | The chart applies its own filter | Pass the chart's own filter as `skip` |
| All charts go blank when the last category is unselected | `IN $room_types` with `[]` matches nothing | Set the param to `null` when the list empties; add the clause only for a non-empty list |
| The map goes empty when a filter is set | The filter's `attr` is not a column in the rows (a feature without the property fails the filter) | Use the exact column name the UDF returns |
| The map does not filter, the charts do | The map spec's `$name` differs from the name the script sets (`$pmin` vs `p_min`) | Same names in both, see the table |
| Shift+drag on the map does nothing | No `selectParam` on the map | Add `"selectParam": "selected"` |
| Shift+click selects a point but the charts ignore it; `selected.ids` is `[]` | The rows have no `id` column and `selectKey` is not set | Set `"selectKey"` to your id column |
| A box counts fewer rows than are inside it | Filtering a box by `ids`: they are the features the map picked, and overlapping points are missed (954 of 1,876 rows in one test box) | Filter `mode: "box"` by `bbox`; use `ids` only when `bbox` is `null` |
| An old result overwrites a newer one after quick clicks | Calls with different SQL do not cancel each other | Generation counter, or one `opts.key` per chart |
| `canvas validate` says `{{ref}} references unknown node 'listings'` | Validate checks `{{name}}` against node names only | `[validate] skip = ["widget_refs"]`, then check the names by hand |
| `json-ui validate` prints `"valid": false` for `"min": "$p_min"` | The deployment predates `$param` filters | Validate with `--env` set to the deployment you push to. If that one rejects it, the feature is not deployed there. The command exits 0 either way: read `"valid"` |
| On a share page the map shows `Running` after every filter change | Expected on share pages, see [Sharing](#sharing) | Nothing to change in the page; keep the UDF cheap |

## Iframe environment

- `sandbox="allow-scripts"`: opaque origin, no cookies, no `localStorage`, no same-origin fetch to the app. All canvas communication goes through `fused.*`. Outbound `fetch` to HTTPS APIs that permit cross-origin requests (the sandbox sends `Origin: null`) and CDN scripts (`<script src="https://cdn.jsdelivr.net/...">`) work.
- The host eats ctrl/cmd-wheel and pinch zoom; wheel scrolling inside the page works.
- The iframe is a blank canvas: set `body` margin, font, background, and color explicitly. Prefer CSS variables on `:root`.
- The iframe fills the node (`width` × `height` from `canvas.toml`). Size the node to the content; start around 800×600 for a dashboard.
- Preserve existing structure, ids, and wiring when editing an existing node unless the request requires a broader rewrite.

## Sharing

- `fused workbench canvas share <canvas>` prints `https://<host>/canvas/<token>`. Each HTML node is then also reachable standalone at `https://<host>/share/<token>/<udfName>` — the same route JSON-UI widgets use.
- Query params hydrate canvas params on load: `?city=Paris&limit=5&bbox=[1,2,3,4]`. `true`/`false` → booleans, numeric strings → numbers, `{...}`/`[...]` → parsed JSON, otherwise string. HTML nodes accept **any** param name from the URL (because `fused.params.set` can broadcast any name), and `set` calls sync back into the URL.
- On the share page `runPython` runs through the share token, `{{udf}}` sources are pre-warmed, and `fused.env` is still `"workbench"`.
- On the share page every param in the URL, including the ones the page sets and a map's `selectParam` value with all its ids, is also sent with each UDF run. A `fused-map` layer therefore runs its UDF again whenever a param changes (the map shows `Running`), although its filters and `fused.query` need no run. A box over most of San Francisco produced a 29,472-character run URL.

## Debug and verify with the CLI

Confirm auth first: `fused workbench whoami`.

1. **Validate the folder**: `fused workbench canvas validate ./my_canvas` (also runs automatically on `push`). It checks node/file pairing and edge endpoints. It does **not** check `.html` files: `{{udf}}` refs, `$params` and `fused.runPython` names in HTML are not verified. Check them yourself:
   ```sh
   grep -oE '\{\{ *[A-Za-z_][A-Za-z0-9_-]*|fused\.runPython\( *["'"'"'`][^"'"'"'`]+' my_canvas/*.html | sort -u
   ```
   Every name must be a `udfName` in `canvas.toml` with an edge into the HTML node, or a `fused-map` layer id or `sql-runner` name in reach. Names a page builds at runtime for `fused.query` are not in the grep: check them against the layer ids by eye.
2. **Push**: `fused workbench canvas push ./my_canvas --canvas <name>`.
3. **Render headlessly**: `fused workbench canvas share <name>` then
   ```sh
   fused workbench json-ui run-shared-widget <token> <html_node_name> --wait 5 --screenshot-filename out.png
   ```
   Works for HTML nodes exactly as for JSON-UI widgets. Prerequisites and limits:
   - **The canvas access scope must be `public`.** `canvas share` mints the token but leaves the scope at `team`, and the headless browser is anonymous, so the page shows `Error loading shared widget: {"detail":"This canvas is not shared publicly."}`. Set the scope to public in the Workbench share dialog (an `_shared.fused` file is not applied by `canvas push`). A logged-in browser can open a team-scoped share link.
   - Selenium must be importable by the `fused` CLI (`ImportError: selenium is required for JSON-UI run` otherwise — install the extras the error names, or run the same URL in your own headless Chrome).
   - Add `?name=value` params by opening the URL from `--print-url-only`. Page `console.log` output is **not** surfaced by the CLI; use the browser devtools on the canvas or the share page.
4. **Iterate on a snippet without pushing**: `fused workbench json-ui run-inline-widget <token> '{"type":"html","props":{"value":"<h1>$name</h1>"}}'` renders the JSON-UI `html` widget, which uses the same bridge and substitution. It has no node of its own, so (from the source, not exercised) edge gating appears to be open there — a snippet that works inline can still fail `not_allowed` once it is a node without the edge.

Do not report success from `validate` alone: it checks structure, not rendering or data. Look at the screenshot or the page.

## Choosing the right construct

| Need | Use |
|---|---|
| Custom interactive UI, JS logic, calls several UDFs, drives other nodes | **HTML template node** (`.html` file) |
| A small HTML snippet inside a JSON-UI layout (next to charts, inputs) | JSON-UI `html` widget (`{"type":"html","props":{"value":"..."}}`) — same bridge and substitution, lives inside a `.json` widget |
| Embed an external site or a UDF that returns a full HTML page, no scripting against the canvas | JSON-UI `iframe` widget (`src: "https://..."` or `src: "{{udf}}"`) |
| Generate HTML server-side from Python (Jinja, folium, plotly `to_html`) | Python UDF returning a `str`; show it via `{{udf}}` in an HTML node, the `iframe` widget, or its own node output |
| Standard controls, charts, tables, maps with no custom code | JSON-UI widgets (see `json-ui-schemas`) |
| A standard widget (control, chart, table, map) inside a custom page | `<fused-widget>` element in the HTML node (see [Embedding widgets](#embedding-widgets-with-fused-widget)) |
| A map whose filters and box selection drive custom charts, and the reverse (cross-filter) | One HTML node: a `fused-map` in `<fused-widget>`, charts drawn by the page from `fused.query` over `{{layer_id}}` (see [Cross-filtering](#cross-filtering-a-map-with-custom-charts)) |

## Not fused-render

The fused-render desktop runtime also exposes `window.fused`, but with a different contract. Do not mix them up when a page is shared between the two:

| | Workbench HTML node | fused-render view |
|---|---|---|
| `fused.env` | `"workbench"` | `"local"` / `"hosted"` |
| `runPython` target | canvas UDF **node name** | path to a sibling `.py` |
| `params` values | any JSON value | strings only (`set("n", 5)` throws) |
| Rejection extras | `.type`, `.message` | `.type`, `.message`, `.traceback`, `.stdout` |
| Uncaught `runPython` rejection | silent | red traceback overlay |
| Files / AI / capture / jobs | not available | available |

Branch on `fused.env === "workbench"` when one page must run in both.

## Pitfalls checklist

- `ReferenceError: fused is not defined` while `window.fusedCanvas` exists → that workbench build predates the `window.fused` bridge (production was in this state on 2026-09-29; unstable had the bridge). Nothing in this skill applies until it is redeployed; do not hand-roll a `fusedCanvas` fallback.
- `$x` in markup **and** `fused.params` on `x` → reload loop / lost state.
- `${name}` or `$$` in markup expecting substitution or escaping — only bare `$name` works in the page.
- `$identifier` in JavaScript colliding with a canvas param name.
- Bare `{{udf}}` on a hidden (`visible = false`) or never-run UDF → `Loading...` forever.
- Forgetting the edge in `canvas.toml` → `not_allowed`, `undefined` params, empty `{{udf}}`.
- `fused.runPython` name built dynamically → no inferred edge in the UI; add it by hand.
- Reading a control's value in `draw()` instead of the param.
- Not catching `runPython`; treating `.type === "aborted"` as an error.
- Expecting `{{udf}}` (columnar object) and `runPython` (array of rows) to have the same shape.
- Unannotated numeric UDF params arriving as strings.
- Assuming fused-render members exist (`readFile`, `rawUrl`, `ai`).
- `<script src>` to a relative path (silent 404, dead page).
- Cross-filter pages: see [Mistakes and their symptoms](#mistakes-and-their-symptoms).
- Relying on `localStorage` / cookies inside the sandbox.
