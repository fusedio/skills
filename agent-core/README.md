# agent-core

A self-contained [Claude Code](https://claude.com/claude-code) plugin for working with **Fused** — end-to-end data work on cloud-native datasets via the `fused` CLI. It bundles the usage/guide skills that take you from a fresh install to a running, deployed project, with no other repo required.

These skills are written to **drive the `fused` CLI** from an agent (Claude Code). They are not consumed by the Fused app/UI.

## Install

Load the repo as a plugin:

```sh
claude --plugin-dir /path/to/agent-core
```

The manifest at [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) points at the [`skills/`](skills/) directory (`"skills": "./skills"`), so every skill below loads at once. Each skill is also self-contained and usable on its own.

## Where to start

- **Set up Fused** → [`fused-setup`](skills/fused-setup/) (then [`fused-infra`](skills/fused-infra/) to provision resources).
- **Build a project end-to-end** → [`fused-projects`](skills/fused-projects/) (then [`fused-execute`](skills/fused-execute/) and [`fused-verify`](skills/fused-verify/) for running and checking code).
- **Not sure which skill?** Load [`fused-guide`](skills/fused-guide/) — it routes your goal to the right skill.

## Skills

| Skill | Purpose |
|---|---|
| [`fused-guide`](skills/fused-guide/) | Entry-point router — maps a goal (set up / build a project / run code) to the right skill. |
| [`fused-setup`](skills/fused-setup/) | Install and set up Fused for the first time — which extras to install, AWS credential checks, provision, verify. |
| [`fused-infra`](skills/fused-infra/) | Reference for the infrastructure Fused manages (AWS: IAM, Lambda, ECR, S3; local: data dirs + venvs) — what exists, why, and when it changes. |
| [`fused-cli`](skills/fused-cli/) | The `fused` CLI reference — environments, file storage, secrets, code execution, projects, share links, `app serve`, infra commands, host extras. |
| [`fused-projects`](skills/fused-projects/) | The canonical end-to-end guide — pick an env, create a project, decompose into UDFs, author specs + code, validate, run/preview, deploy. |
| [`fused-execute`](skills/fused-execute/) | Best practices for running code with `fused code run` — structuring code, choosing a data library, handling results, writing outputs. |
| [`fused-verify`](skills/fused-verify/) | Static scanning, spec checks, tests, and the audit log (`fused code verify`, `fused code test`, `fused audit log`). Verification does not run automatically. |
| [`fused-storage`](skills/fused-storage/) | Storage + secrets CLI commands (`fused files …`, `fused secrets …`) — inspect cloud-native datasets and manage secrets. |

> **CLI only.** `fused` no longer ships a general MCP server (no `mcp__openfused__*` tools), JSON-UI widgets, `dev serve`, or a built-in `_core` workspace. The only MCP surface is `fused app serve <dir>` (see [`fused-cli`](skills/fused-cli/)).

## Customizing & contributing

Two kinds of change, handled in opposite ways — see [`CONTRIBUTING.md`](CONTRIBUTING.md):

- **Changing what a skill *means*** (new defaults, a repurposed op, a
  team-specific workflow) → **don't edit the shipped skill.** Create a new skill
  or Fused project in **your own workspace** and diverge there.
- **Fixing a bug or adding to a skill** (doc fix, wrong/missing field, an
  additive op) → **contribute it back as a PR** so the fix lands upstream instead
  of living as a local divergence.
