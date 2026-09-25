---
name: fused-guide
description: Entry-point router for the Fused skills in this repo. Use when a user asks how to get started with, set up, or install Fused, how to build a project or UDF, how to run or validate code with the `fused` CLI, or is unsure which Fused skill to load. Maps a goal to the specific skill(s) to read next.
---

# Fused — start here

This repo is a Claude Code plugin for **Fused** (end-to-end data work on
cloud-native datasets via the `fused` CLI). The model is **workspace ⊃ project ⊃
UDF**. This guide routes your goal to the skill that covers it — load that skill
and follow it. Don't try to do the work from this page; it only points.

> **CLI only.** Fused no longer ships a built-in MCP server: there are no
> `mcp__openfused__*` tools, and a bare `fused` just prints help. All data work goes
> through `fused <group> <command>` in the shell. The only MCP surface left is
> `fused app serve <dir>`, which serves the tools declared in an app folder's
> `mcp.toml` (see `fused-cli`).

## Pick by goal

### Set up / install Fused
1. **`fused-setup`** — install the package (and the right extras for what you need),
   check AWS credentials (or pick the local backend, no cloud needed), create an
   environment, and verify.
2. **`fused-infra`** — what infrastructure each backend provisions (AWS: IAM,
   Lambda, ECR, S3; local: data dirs + venvs), and how to provision/troubleshoot it.

### Build a project end-to-end
This is the main path from a user request to a running result.
- **`fused-projects`** — the canonical end-to-end flow: pick an environment,
  create a project, decompose the task into UDFs, author specs + code, validate,
  commit, run, and deploy. Start here for any "take this from prompt to result"
  request.

### Run and validate code
- **`fused-execute`** — best practices for `fused code run`: structuring user
  code, choosing a data library, handling results, writing outputs to storage.
- **`fused-verify`** — static checks, spec checks, tests and the audit log
  (`fused code verify`, `fused code test`, `fused audit log`).
- **`fused-storage`** — inspect datasets (list/count files, read schemas,
  mint download URLs, upload) and manage secrets (`fused files …`,
  `fused secrets …`).

### Reach for the CLI
- **`fused-cli`** — full `fused` command/flag reference: environments,
  file storage, secrets, code execution, projects, share links, app serving,
  infra. Use when writing or explaining shell commands that invoke `fused`.

## Customizing or fixing a skill

Before editing any skill in this repo, pick the right path (see `CONTRIBUTING.md`):

- **Changing what a skill *means*** — different defaults, a repurposed UDF op, a
  team-specific workflow — **do not modify the shipped skill in place.** Create a
  new skill or Fused project in the user's own workspace and diverge there;
  an in-place meaning change affects everyone who loads this plugin and is lost
  on the next pull. Tell the user this and author the new skill/project instead.
- **Fixing a bug or making an additive improvement** — a doc fix, a wrong/missing
  field, a clarified caveat, a genuinely additive op — **contribute it back as a
  PR** (branch off `main`, focused change, behavior-preserving). Tell the user to
  upstream it rather than keep a local divergence.
