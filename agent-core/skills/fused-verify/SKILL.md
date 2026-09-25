---
name: fused-verify
description: Static scanning, spec checks, testing, and the audit log for code run with fused. Use when running or reviewing `fused code verify`, `fused code test`, or `fused audit log`, or when advising on what fused's verify layer does (and no longer does). If you're validating code that belongs to a project, load `fused-projects` first for the end-to-end flow.
---

# Scanning, testing, and validation in fused

> **Part of the Fused skill set — don't work from it alone.** Fused is `workspace ⊃
> project ⊃ UDF`. If you're validating code that belongs to a project, load
> **`fused-projects`** for the end-to-end flow (specs, run, deploy) and
> **`fused-execute`** for how code runs. See **`fused-guide`** for the full set.

## What exists today

| Layer | Command | What it checks |
|---|---|---|
| Static scan | `fused code verify` | Code patterns, dependency CVEs/typosquats, input-file names and zip bombs |
| Spec conformance | `fused code verify --spec "..."` | LLM check: does the code match the stated intent? |
| Test suite | `fused code test --test-file …` | Pytest + line/branch coverage in the real execution environment |
| Audit | `fused audit log` | Reads the local audit store (see below for what is still recorded) |

> **Verify does not run automatically.** `fused code run` and `fused code test`
> execute code **without** any pre- or post-execution scan. Nothing blocks a run,
> no output firewall inspects results, and no `execute_code` / `verify_code`
> audit events are written. The environment's verify settings (`--verify`,
> `--require-spec`, `--audit-bucket`, `verify.enabled`, `block_on_warn`,
> `typecheck`, `expectations`) do **not** gate or check executions. If you want a
> scan, run `fused code verify` yourself before `code run`.
>
> There is also no CLI replacement for the old data-quality `expectations`
> contract (schema / null-rate / row-count / bounds checks on a result). Check those
> in your own code or in a `code test` test file.

---

## Static scan (`fused code verify`)

`code verify` scans code and input files **without executing** anything. Use it
before `code run` to catch problems early, or as a gate in CI — it exits 1 when
any BLOCK finding is produced.

```sh
fused code verify my_udf.py
fused code verify -c "import os; result = os.listdir('/')"
cat my_udf.py | fused code verify
fused code verify my_udf.py --project my-project        # scan the project's deps (local)
fused code verify my_udf.py --input-file ./data.zip     # also check an input archive
```

Output is one line per finding — `[WARN] code/dangerous-import: …` — then a
`N block  N warn  N info` summary, or `No findings.`.

What it runs, in order:

1. **Input firewall** (only with `--input-file`) — path traversal in the filename
   and zip-bomb detection. The filename checked is the file's basename, so in
   practice the zip-bomb check is the one that fires.
2. **Code scanner** — AST pattern matching (`code/*` rules).
3. **Spec scanner** (only with `--spec`) — the LLM review below.
4. **Dependency scanner** — OSV CVE lookup plus typosquat check on the
   requirements: the project's `scripts/pyproject.toml` deps with `--project` /
   `--project-dir` (local), otherwise the environment image's packages (AWS). No
   requirements means nothing to scan.

What it does **not** run: the type checker (`code/type-error`), input-file PII
detection (`input/pii`), the `spec/required` policy, and anything
post-execution. It writes no audit event.

The environment's verify config still supplies two things to `code verify`:
per-rule severity overrides (`rules`) and the OSV endpoint.

> **Advisory, not a sandbox.** The code scan is static (AST) pattern matching. It
> catches honest mistakes and low-effort misuse, but it is **not a containment
> boundary** — a dynamic lookup such as `importlib.import_module("subprocess")` or
> `getattr(builtins, "exec")` slips past it, and a BLOCK finding only means *this
> scanner* refused. The real isolation for executed code is the per-call
> subprocess plus the execution role's IAM scope (AWS); the local backend has no
> isolation boundary at all. Scope the IAM role tightly; do not rely on verify
> findings as your security perimeter.

### Rule reference

| Rule ID | Severity | Emitted by `code verify`? | What triggers it |
|---|---|---|---|
| `code/dangerous-import` | WARN | yes | `import os`, `import sys`, `import subprocess`, `import socket`, etc. |
| `code/exec-eval` | BLOCK | yes | `exec(...)` or `eval(...)` calls |
| `code/__import__` | BLOCK | yes | `__import__(...)` call |
| `code/network-import` | WARN | yes | `urllib`, `requests`, `httpx`, `boto3`, `aiohttp`, etc. |
| `code/credential-string` | BLOCK | yes | Hard-coded credential string detected |
| `code/path-traversal` | WARN | yes | Path traversal pattern in a string literal |
| `code/sql-injection` | WARN | yes | String concatenation inside a SQL call |
| `code/syntax-error` | BLOCK | yes | Code fails to parse |
| `dep/cve` | WARN | yes | Known CVE in a scanned package |
| `dep/typosquatting` | WARN | yes | Package name resembles a well-known package (e.g. `numppy`) |
| `dep/osv-unavailable` | INFO | yes | OSV vulnerability database unreachable |
| `input/path-traversal` | BLOCK | yes (`--input-file`) | Input filename contains `..` sequences |
| `input/zip-bomb` | BLOCK | yes (`--input-file`) | Input archive expands to an unsafe size |
| `spec/mismatch` | BLOCK | yes (`--spec`) | LLM judges the code doesn't match the spec |
| `spec/review-error` | WARN | yes (`--spec`) | LLM call failed (missing key, missing `verify` extra, API error) |
| `input/pii` | WARN | no | — |
| `code/type-error` | WARN | no | — |
| `spec/required` | BLOCK | no | — |
| `output/*`, `correctness/*` | — | no | Post-execution checks; nothing runs them now |

---

## Spec conformance (`--spec`)

Pass `--spec` to have Claude review whether the code matches a natural-language
description of intent:

```sh
fused code verify my_udf.py --spec "return the number of rows in the dataset"
# [BLOCK] spec/mismatch: …   → exit 1
```

For a project UDF, pass the contents of its `scripts/<udf>/spec.md`:

```sh
fused code verify my-proj/scripts/taxi-analysis/main.py \
  --spec "$(cat my-proj/scripts/taxi-analysis/spec.md)"
```

When to use spec checks:
- Agent-generated code that should match a user's stated goal
- High-stakes transformations where incorrect code would silently produce wrong results
- Before running expensive or destructive code

Requirements:
- The **`verify` extra** on the host (`fused[verify]`, which installs `anthropic`).
  Without it the check emits a `spec/review-error` warning instead of a verdict.
- An Anthropic API key, resolved in order: `ANTHROPIC_API_KEY` (or
  `ANTHROPIC_AUTH_TOKEN`) in the shell, then the `anthropic-api-key` secret in the
  resolved environment. Store it with `fused secrets put anthropic-api-key` (it
  prompts — never pass the key on the command line). On AWS the name must carry the
  env's prefix, e.g. `openfused-anthropic-api-key`. With no key, you get a
  `spec/review-error` warning.

---

## Testing code (`fused code test`)

`code test` runs a pytest file against user code **inside the real execution
environment** (Lambda on AWS, the project venv on local). This catches import
errors, missing packages, and runtime behaviour static analysis misses.

```sh
cat > test_add.py <<'EOF'
from user_code import add

def test_add_integers():
    assert add(1, 2) == 3

def test_add_floats():
    assert abs(add(1.1, 2.2) - 3.3) < 1e-9
EOF

fused code test -c "def add(a, b): return a + b" --test-file test_add.py
fused code test my-proj/scripts/adder/main.py --test-file test_add.py --project my-proj
```

Output: the run's stdout/stderr and `warning:` lines, then
`N passed  N failed  N errors  N skipped` and `coverage: NN% lines  NN% branches`.
Exits 1 if any test fails.

**Rules for the test file:**
- Import user code via `from user_code import <name>` — the module is always named
  `user_code`.
- Standard pytest conventions apply: `test_` functions, `assert`, fixtures.
- **AWS:** pytest and coverage are installed automatically on first use.
- **Local:** the project venv must already have them. Add them as dev deps:
  `fused project add-dep <project> pytest coverage --dev`.
- `--input-file PATH` (repeatable) stages extra files next to the code.

Use `code verify` for a fast security pre-screen (no cold start) and `code test`
for behavioural confidence. They are complementary: verify first, then test.

---

## Audit log (`fused audit log`)

`fused audit log` reads the local SQLite store at `~/.openfused/audit.db`:

```sh
fused audit log --limit 20
fused audit log --event-type cache_clear
fused audit log --status blocked --project my-proj
```

Flags: `--limit` (default 50), `--event-type`, `--status allowed|blocked|warned`,
`--project`. There is no date-range filter and no S3 merge.

**What is still recorded:** `cache_clear` events (from `fused share cache-clear`)
and share-mount lifecycle events (create / revoke / recreate / repoint).
`code run`, `code test` and `code verify` write nothing, so filtering by
`--event-type execute_code` or `verify_code` only returns events from older
installs.

---

## Recommended workflow for production code

1. **`fused code verify <file> --spec "…"`** — pre-screen for security issues and
   spec conformance. Treat a non-zero exit as a stop.
2. **`fused code test <file> --test-file <tests>`** — run the test suite, including
   any schema / row-count / bounds assertions you care about; require a zero exit
   before deploying.
3. **`fused code run <file>`** — execute.
4. **`fused udf deploy` / `fused project deploy`** — see fused-projects.
