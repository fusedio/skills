---
name: html-template-nodes
description: Authoring reference for Fused canvas HTML template nodes — the `.html` file in a canvas folder that renders as a sandboxed iframe with `window.fused` (`fused.params`, `fused.runPython`) and `$param` / `{{udf}}` substitution. Use when creating, editing, debugging, wiring, or sharing an HTML node, when a page needs to read canvas params or call a canvas UDF from JavaScript, or when deciding between an HTML node, the JSON-UI `html` widget, the `iframe` widget, and a Python UDF that returns HTML.
---

# Fused canvas HTML template nodes

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
x = 750
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

Applied to the HTML string before the iframe loads.

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
| Not available | `readFile`, `writeFile`, `stat`, `rawUrl`, `ai`, `fileIndex`, `capture`, `trackJob`, `daemon`. These members are simply absent (`typeof fused.readFile === "undefined"`), so calling them throws a `TypeError`. Anything needing files or Python goes in a UDF; call it with `runPython`. |

### `fused.runPython` details

- `params` values are sent as strings (non-strings JSON-encoded). Annotate the UDF's parameters (`n: int`, `bbox: list`, `flag: bool`) so they coerce; unannotated numeric params arrive as strings.
- Your params merge over the UDF's own panel values (yours win, the panel fills the gaps) — same as `{{udf?k=v}}`.
- **Stale-cancel by default, keyed per `udfName`**: a newer call supersedes the in-flight one and the superseded promise **never settles**. `opts.key` regroups (`{ key: "chart-a" }`), `opts.key: null` allows full concurrency, `opts.signal` is your own `AbortSignal` (rejects with `.type === "aborted"`).
- Error types: `not_allowed` (no edge from a node with that name into this node — this is also what a misspelled or non-existent name produces, since the edge check runs first), `not_found` (edge exists but the node is gone), `no_environment` (workbench has no active execution environment yet), `invalid_args`, `udf_error` (the UDF raised; `.message` has the error text), `aborted`.
- Always `try/catch` and render the error into the page. Uncaught rejections are silent — there is no traceback overlay in the workbench.
- On the canvas the call runs the **live** node code through the authenticated realtime path. On a share page it runs through the canvas share token (no execution environment needed).
- When a connected source UDF finishes a new run, the host **reloads the iframe** so `runPython` calls refetch. Design `draw()` to be re-runnable from scratch. The node toolbar's "Invalidate cache" / run button also just reloads the iframe.

## Edges

Visibility follows canvas edges. This node sees params from, and may `runPython` against, **only UDF nodes with an edge into it** (bidirectional edges count both ways).

- No edge → `runPython` rejects `not_allowed`, `params.get` is `undefined`, `{{udf}}` renders empty.
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
  async function draw(p) {
    city.value = p.city ?? "";
    limit.value = String(p.limit ?? 10);
    if (!p.city) { out.textContent = "Pick a city"; return; }
    out.textContent = "Loading…";
    try {
      const rows = await fused.runPython("city_stats", { city: p.city, limit: Number(p.limit ?? 10) });
      out.textContent = rows.map(r => `${r.name}: ${r.value}`).join("\n");
    } catch (e) {
      if (e.type === "aborted") return;
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
- Coerce in `draw()` (`Number(p.limit)`): params set by another node or hydrated from a share URL may arrive as strings, numbers or JSON depending on origin.
- Before writing rendering code for an unknown result shape, `console.log` the first `runPython` result (open the browser devtools on the canvas) — do not invent column names.
- Keep data preparation in Python UDFs; the page renders and coordinates UI behaviour.

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

## Debug and verify with the CLI

Confirm auth first: `fused workbench whoami`.

1. **Validate the folder**: `fused workbench canvas validate ./my_canvas` (also runs automatically on `push`). It checks node/file pairing and edge endpoints. It does **not** check `.html` files: `{{udf}}` refs, `$params` and `fused.runPython` names in HTML are not verified. Check them yourself:
   ```sh
   grep -oE '\{\{ *[A-Za-z_][A-Za-z0-9_]*|fused\.runPython\( *["'"'"'`][^"'"'"'`]+' my_canvas/*.html | sort -u
   ```
   Every name must be a `udfName` in `canvas.toml` with an edge into the HTML node.
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
- Relying on `localStorage` / cookies inside the sandbox.
