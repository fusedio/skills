# Fused Plugins for Claude Code

The `fused-marketplace` ships two Claude Code plugins:

- **[`agent-core`](agent-core/)** — the primary plugin. Usage/guide skills for building with **Fused** end-to-end: setup, infra, the `fused` CLI, project authoring, execution, verification, and storage.
- **[`workbench`](workbench/)** — legacy skills for the Fused **workbench** SDK CLI (`fused workbench …`): canvas.toml, JSON-UI widgets, UDFs, and integrations.

> **Heads up — CLI namespace change.** The original Fused repo was consolidated with OpenFused and now ships as a single `fused` package. The bare `fused` command is now the **OpenFused agent toolkit**; the legacy proprietary SDK CLI now lives under **`fused workbench`** (e.g. `fused canvas push` → `fused workbench canvas push`). The package name is unchanged; see below for which extras to install.

## Install the plugins

```sh
claude plugin marketplace add fusedio/claude-plugins
claude plugin install agent-core@fused-marketplace   # primary
claude plugin install workbench@fused-marketplace      # legacy workbench skills
```

To update or remove:

```sh
claude plugin update agent-core@fused-marketplace
claude plugin remove agent-core
# Or, for the entire marketplace:
claude plugin marketplace remove fused-marketplace
```

You can also load a plugin directly from a local checkout without the marketplace:

```sh
claude --plugin-dir ./agent-core
```

## Installing the `fused` CLI

Both plugins drive the `fused` CLI. Install it once, with the extras for what you'll use:

```sh
uv tool install 'fused[aws]'          # agent-core on an AWS environment
uv tool install 'fused[aws,verify]'   # ...plus `fused code verify --spec`
uv tool install 'fused[geo]'          # workbench SDK (geopandas, shapely, pandas)
```

Then open a new Claude Code session. `fused` is now permanently on your PATH — Claude can find it in any future session without reinstalling.

Plain `uv tool install fused` gives you the CLI with the local backend and `fused app serve`. The extras add:

| Extra | Needed for |
|---|---|
| `data` | pyarrow, pandas, numpy: `fused files schema`, and `fused.run()` returning a DataFrame |
| `aws` | any AWS environment (Lambda, S3, Secrets Manager, `infra`, `share` on AWS); includes `data` |
| `verify` | `fused code verify --spec` (the LLM spec check, via anthropic) and the `ty` type checker |
| `geo` | the workbench SDK's geo stack (geopandas, shapely, rasterio, xarray, ...); includes `data`. `vector`, `raster` and `batch` still work as aliases |
| `workbench` | selenium and fastmcp for the `fused workbench` CLI's JSON-UI and MCP commands |
| `local` | local-backend secrets on hosts with no OS keychain (Linux/WSL) |
| `all` | everything except `local` |

Extras are host packages only. Code you run on Lambda or in a project venv gets its packages from the environment image (`fused env update -p …`) or the project (`fused project add-dep …`).

If `uv` is not found, install it first, then re-run the commands above:

- **macOS / Linux:** `curl -LsSf https://astral.sh/uv/install.sh | sh` (restart terminal after)
- **Windows:** `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` (restart terminal after)

### Reinstall / update the CLI

```sh
uv tool install 'fused[aws]' --upgrade   # same extras you installed with
```

### Alternative: pip

If Python 3.10+ is already installed and you prefer not to use `uv`:

```sh
pip install --upgrade 'fused[aws]>=2'
```

> **Python 3.9 note:** `pip install fused` on Python 3.9 silently installs `fused 1.x`, which has no `fused` command. Pinning `>=2` makes pip fail loudly instead. Use `uv tool install` above to avoid this entirely.

#### Windows (pip path)

If `fused` is not found after `pip install`, the Scripts directory is likely missing from your PATH. Run:

```powershell
python -m site --user-scripts
```

This prints the exact Scripts path (e.g. `C:\Users\You\AppData\Roaming\Python\Python311\Scripts`). Add it to your `PATH` (search "environment variables" in the Start menu → edit the `Path` user variable), then open a new terminal and retry.
