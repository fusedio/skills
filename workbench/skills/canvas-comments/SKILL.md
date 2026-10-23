---
name: canvas-comments
description: Use when a Fused canvas.toml contains (or needs) a [[canvas.comments]] block — e.g. the user asks to check/fix/resolve canvas comments, review feedback pins on a canvas, or leave comments on a canvas for someone else. Covers reading, writing, and resolving comments via the fused CLI pull/push workflow.
---

# Fused canvas comments ([[canvas.comments]] in canvas.toml)

> **CLI version:** commands below are written `fused workbench …` (only the 2.9.2b0+ pre-releases have this namespace; released versions such as 2.9.1 and 2.9.3 don't). If `fused workbench` fails with `No such command 'workbench'`, drop the word `workbench` — e.g. `fused canvas push`. See `fused-workbench-cli`.

Pinned comment threads on a Fused canvas serialize as `[[canvas.comments]]` blocks in `canvas.toml`.
Top-level `[[comments]]` blocks are silently dropped by `canvas push`.
If `[canvas]` has `comments = []`, delete that line first: both in one file fail to parse ("duplicate key").

Comments with `status = "open"` are your work queue; resolving one is a three-field contract plus a reply, so the Workbench UI correctly attributes the work to AI.

## Read: find the work

1. Get the canvas locally: `fused workbench canvas pull <name> -o <dir>` (or use the folder you have).
2. Every `[[canvas.comments]]` block where `status = "open"` is an actionable request.
3. `anchor_udf = "<udfName>"` tells you WHICH node it's about — the fix belongs in `<udfName>.py` (or `.json`/`.md`/`.html` with that stem). No `anchor_udf` ⇒ canvas-level comment; read `content` for scope.

## Resolve: the full contract (all four steps, not just status)

After actually making the fix the comment asks for:

```toml
[[canvas.comments]]
id = "cmt-a"                      # never change existing ids
# ...existing fields stay untouched...
status = "resolved"               # 1. was "open"
resolved_by = "ai"                # 2. REQUIRED — this is what shows the AI badge in the UI
resolved_at = 1749600200000       # 3. ms epoch timestamp (date +%s000)

[[canvas.comments.replies]]              # 4. say what you did
id = "reply-<unique>"
content = "Changed the default to 7. Done."
created_at = 1749600200000
created_by = "ai"                 # REQUIRED on AI-written replies
```

**Setting only `status = "resolved"` is wrong** — without `resolved_by = "ai"` the UI cannot attribute the resolution, and without a reply the user doesn't know what changed.

## Write: adding a new comment

```toml
[[canvas.comments]]
id = "cmt-<unique>"               # required, stable, unique in file
x = 120.0                         # required: canvas coords (floats)
y = 80.0
anchor_udf = "process_data"       # optional: node NAME (matches a [[canvas.nodes]] udfName)
offset_x = 24.0                   # only meaningful with anchor_udf
offset_y = 16.0
content = "non-empty text"        # blank content is silently dropped
status = "open"
created_by = "ai"                 # REQUIRED when you author it
created_at = 1749600000000        # ms epoch
```

## Field reference (snake_case in TOML — never camelCase)

| Field | Notes |
|---|---|
| `id`, `content`, `x`, `y` | required; blank/whitespace `content` ⇒ row dropped on parse |
| `status` | `open` \| `resolving` \| `resolved`; omitted ⇒ `open` |
| `anchor_udf`, `offset_x`, `offset_y` | anchor by UDF *name*, not node id; unknown name ⇒ anchor silently dropped |
| `created_by`, `resolved_by` | `"user"` \| `"ai"`; omitted = user |
| `created_at`, `updated_at`, `resolved_at` | ms epoch integers |
| `replies` | `[[canvas.comments.replies]]` with `id`, `content`, `created_at`, optional `updated_at`, `created_by` |

Never write a TOML `null`/empty value — omit absent fields entirely. Comments sort by `created_at` on export; don't reorder blocks by hand.

## Verify, then push

```bash
fused workbench canvas validate <dir>        # structure check
fused workbench canvas push <dir> --canvas <name>
```

## Common mistakes

- Resolving without `resolved_by = "ai"` / `resolved_at` / a reply (the #1 miss).
- camelCase keys (`createdAt`) in TOML — the parser ignores them; data silently lost.
- Anchoring by node id instead of `anchor_udf` name.
- Marking `resolved` without actually making the code change the comment asks for.
- Editing/deleting other people's `id`s or `created_at`s — append, don't rewrite history.
