# workbench plugin

Skills for the legacy Fused workbench SDK CLI (`fused workbench …`). Install instructions are in the [repository README](../README.md).

## fused-render marker blocks

fused-render hands these skills to agents working inside a **canvas clone**: a folder fused-render keeps in sync with a canvas on the server, which publishes itself and takes in server changes on its own. Guidance that only fits a standalone folder (pull the canvas first, push then test, `--no-validate`, the directory-name note) is wrong there, so the skills carry two kinds of marker blocks. Both are HTML comments, so a skill read anywhere else reads exactly as it would without them.

- **Strip block.** A line `<!-- fused-render:strip -->`, the standalone-only content, then a line `<!-- /fused-render:strip -->`. fused-render deletes the block, markers included.
- **Only block.** A line `<!-- fused-render:only`, markdown for the clone, then a line holding just `-->`. fused-render deletes the two marker lines and keeps the markdown between them. Everywhere else the whole block is one invisible comment.

Rules:

- Each marker sits alone on its own line, at column 0, with nothing after it. Blocks do not nest.
- Wrap whole block-level units: a whole paragraph, list, table, blockquote or fenced code block. A marker line ends any open paragraph, list or table, so a block that starts or ends partway through one changes how the standalone text renders.
- An only block's body must not contain `-->` (it would end the comment early) or `<!--`.
- Put a blank line before a strip block and after the only block that follows it, so the clone text keeps its spacing once the markers are gone.
- When a strip block has an only twin right after it, the two are copies of the same text with the clone wording swapped in. Edit both when you change either.
- Clone wording: the folder is a live clone kept in sync by fused-render; never pull or push there (both are refused); the canvas publishes itself when the agent's turn ends and whenever the folder goes quiet; server changes arrive in the folder automatically and the session hook names the files; verify with the `canvas_screenshot` tool and `fused workbench canvas validate .`.
- Markers cannot go in YAML frontmatter, so keep `canvas pull` / `canvas push` out of skill descriptions.
