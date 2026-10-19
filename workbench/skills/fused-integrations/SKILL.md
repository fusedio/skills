---
name: fused-integrations
description: Reference for using Fused's built-in integration connections inside UDFs. Covers data sources (Snowflake, BigQuery, GCS, S3, Airtable, Notion, Google Drive), compute/inference providers (Modal, Hugging Face, Baseten, Daytona, ComfyOrg, Slack), and LLM providers (Anthropic, OpenAI) — the fused.api connect helpers, secrets access, and common operations (query, write, list, invoke, infer). Use when the user is writing a UDF that reads from, writes to, or calls out to a connected service.
---

# Fused Integrations

> **CLI version:** commands below are written `fused workbench …` (fused ≥ 2.9.2b0). If `fused workbench` fails with `No such command 'workbench'` (fused 2.9.1 and earlier), drop the word `workbench` — e.g. `fused canvas push`. See `fused-workbench-cli`.

Once an integration is configured (via the Workbench → Integrations UI or `fused workbench integrations <provider> connect`), use the helpers below inside any UDF. You do **not** need to manage credentials manually — connections and secrets are resolved by the runtime.

Available integrations: `snowflake`, `bigquery`, `gcs`, `s3`, `airtable`, `notion`, `gdrive`, `modal`, `huggingface`, `baseten`, `daytona`, `comfy`, `anthropic`, `openai`, `slack` (experimental).

---

## Testing integration UDFs

Integration UDFs have two failure modes general UDFs don't: missing access grants and execution-context differences between `fused workbench run` and public shared URLs. See the `fused-udfs` skill for general testing guidance — the integration-specific additions are below.

**Start with a connectivity smoke test.** Before building any logic, verify the integration actually connects and returns data:

```python
@fused.udf
def udf():
    # Smoke test: verify connection before writing full logic
    nt = fused.api.notion_connect()
    client = nt.client()
    results = client.search(query="", filter={"value": "page", "property": "object"})
    return {"connected": True, "pages_visible": len(results.get("results", []))}
```

**Also test via the shared URL** if the UDF will be served publicly (e.g. `https://udf.ai/fc_TOKEN/udf_name`). Some integrations — notably Notion — behave differently in that unauthenticated execution context. See the Notion section below for details.

---

## External API keys — scope and fallback patterns

A secret stored as `fused.secrets["my_api_key"]` is just a string — the Fused runtime doesn't know which endpoints it covers. Two things to verify before writing logic that depends on a key:

1. **Test the specific endpoint, not just the key.** Many providers (Google, AWS, Stripe) issue keys with per-API or per-product scopes. A key that authenticates successfully against one API may return `403`, `REQUEST_DENIED`, or `PERMISSION_DENIED` on another, even from the same provider. Test each endpoint explicitly in isolation before assuming the key covers it.

2. **Build a primary + fallback chain for critical paths.** If a UDF must geocode, enrich, or classify data and the primary API is unavailable or uncredentialed, having a fallback keeps the rest of the pipeline alive:

```python
@fused.cache
def enrich(item, _v=1):
    # Try primary API
    result = call_primary_api(item)
    if result is not None:
        return result
    # Fall back to alternative (open API, cached copy, degraded mode)
    return call_fallback_api(item)
```

**Rate-limited APIs:** Any external API that enforces per-second or per-minute limits needs an explicit sleep between uncached calls. Wrap each call in `@fused.cache` so the sleep only fires on the first call per unique input; subsequent calls return instantly from cache:

```python
@fused.cache
def call_rate_limited_api(key, _v=1):
    import time
    time.sleep(1.1)  # stay under 1 req/s
    return make_request(key)
```

Without the cache, every UDF run re-fires every API call, burning rate limit and adding latency proportional to the number of unique inputs.

---

## Google Drive

Google Drive access only works inside **cloud UDFs** — local Python raises "Google Drive is not connected" even if CLI list commands work. Connect via Workbench → Integrations → Google Drive (OAuth browser flow), then grant file/folder access via the Picker UI.

### gdrive:// path format

```
gdrive://<folder_id>/<folder_name>/   # list a folder
gdrive://<file_id>/<filename>         # read a specific file
gdrive://root/                        # all Picker-granted files at root
```

### List files

```python
@fused.udf
def udf():
    return fused.api.list("gdrive://root/")
```

### Read tabular files (CSV, Excel)

```python
@fused.udf
def udf():
    import pandas as pd
    return pd.read_csv("gdrive://<file_id>/<name>.csv")
```

```python
@fused.udf
def udf():
    import pandas as pd
    return pd.read_excel("gdrive://<file_id>/<name>.xlsx")
```

Google-native formats are auto-exported: Sheets → `.xlsx`, Docs → `.docx`, Slides → `.pptx`, Drawings → `.png`.

### Read binary files / return to frontend

Base64-encode the raw bytes and return a data URI in the DataFrame — no `fd://` write needed:

```python
import base64, mimetypes, io, pandas as pd

data = fused.api.get(gdrive_path)   # e.g. "gdrive://<id>/<name>.jpg"
file_name = gdrive_path.split("/")[-1]

# Tabular — return DataFrame directly
if file_name.endswith(".csv"):
    return pd.read_csv(io.BytesIO(data))
if file_name.endswith((".xlsx", ".xls")):
    return pd.read_excel(io.BytesIO(data))

# Binary — return as data URI
mime, _ = mimetypes.guess_type(file_name)
data_uri = f"data:{mime or 'application/octet-stream'};base64,{base64.b64encode(data).decode()}"
return pd.DataFrame([{"file": file_name, "size_kb": round(len(data)/1024, 1), "data_uri": data_uri}])
```

Use `data_uri` in the widget as `<img src>`, `<video src>`, or `<embed src>`. For very large files fall back to `fd://` staging + `fused.api.sign_url()`.

### Upload a file to Google Drive from a URL

```python
@fused.udf
def udf():
    import urllib.request, requests

    url = "https://example.com/data.csv"
    folder_id = "root"

    file_name = url.split("?")[0].rstrip("/").split("/")[-1] or "upload.csv"
    with urllib.request.urlopen(url) as resp:
        data = resp.read()
    api = fused.api.api
    creds = api.AUTHORIZATION.credentials
    r = requests.put(
        f"{api.OPTIONS.base_url}/files/upload",
        params={"path": f"gdrive://{folder_id}/{file_name}"},
        data=data,
        headers={
            "Authorization": f"Bearer {creds.access_token}",
            "Content-Type": "application/octet-stream",
        },
    )
    r.raise_for_status()
```

A 401 response means credentials belong to a different user — make a copy of the canvas.

### Parse fused.api.list() results

```python
items = fused.api.list("gdrive://root/")
for item in items:
    stripped = item.replace("gdrive://", "").rstrip("/")
    item_id, item_name = stripped.split("/", 1)
    is_dir = item.endswith("/")
```

---

## Snowflake

Docs: https://docs.fused.io/workbench/integrations/snowflake

### Simple query

```python
@fused.udf
def udf():
    import fused.api
    return fused.api.snowflake_query(
        "SELECT * FROM my_db.my_schema.my_table LIMIT 10"
    )
```

### Reusable connection (multiple operations)

```python
@fused.udf
def udf():
    import fused.api
    conn = fused.api.snowflake_connect(
        warehouse="COMPUTE_WH",
        database="ANALYTICS",
        schema="PUBLIC",
        role="ANALYST",
    )
    print("Tables:", conn.list_tables("ANALYTICS", "PUBLIC"))
    return conn.query("""
        SELECT region, SUM(amount) AS total
        FROM orders
        WHERE order_date >= '2025-01-01'
        GROUP BY region
        ORDER BY total DESC
    """)
```

### Write a DataFrame back to Snowflake

```python
@fused.udf
def udf():
    import fused.api, pandas as pd
    conn = fused.api.snowflake_connect(
        warehouse="COMPUTE_WH", database="ANALYTICS", schema="PUBLIC"
    )
    df = pd.DataFrame({"id": [1, 2, 3], "value": [10.5, 20.3, 30.1]})
    conn.write(df, "ANALYTICS.PUBLIC.METRICS", mode="overwrite")
    return df
```

### Read from a Snowflake Stage

```python
@fused.udf
def udf():
    import fused.api
    conn = fused.api.snowflake_connect(
        warehouse="COMPUTE_WH", database="RAW_DATA", schema="INGEST"
    )
    files = conn.list_stage_files("@csv_stage", pattern=".*[.]csv")
    if files:
        return conn.read_stage(f"@csv_stage/{files[0].split('/')[-1]}")
```

**Connection methods:** `.query()`, `.list_tables()`, `.write(df, table, mode=)`, `.list_stage_files()`, `.read_stage()`

---

## BigQuery

Docs: https://docs.fused.io/workbench/integrations/bigquery

Credentials are stored as a service-account JSON string in `fused.secrets["gcs_fused"]`.

```python
@fused.udf
def udf():
    import json
    from google.cloud import bigquery
    from google.oauth2 import service_account

    credentials = service_account.Credentials.from_service_account_info(
        json.loads(fused.secrets["gcs_fused"]),
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    client = bigquery.Client(credentials=credentials, project=credentials.project_id)
    query = """
        SELECT * FROM `bigquery-public-data.new_york.tlc_yellow_trips_2015`
        LIMIT 10
    """
    return client.query(query).to_dataframe()
    # For geospatial results: .to_geodataframe(geography_column="geometry")
```

---

## Google Cloud Storage (GCS)

Docs: https://docs.fused.io/workbench/integrations/gcs

Credentials are stored as a service-account JSON string in `fused.secrets["gcs_fused"]`.

### List files in a bucket

```python
@fused.udf
def udf():
    import os
    from google.cloud import storage

    with open("/tmp/gcs_key.json", "w") as f:
        f.write(fused.secrets["gcs_fused"])
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/tmp/gcs_key.json"

    client = storage.Client()
    bucket = client.bucket("your_bucket_name")
    blobs = bucket.list_blobs(prefix="path/to/your/data")
    print({blob.name for blob in blobs})
```

---

## Amazon S3

Docs: https://docs.fused.io/workbench/integrations/s3

S3 access is granted via IAM role (configured once in the Integrations UI). No credentials are needed inside the UDF.

### List files

```python
@fused.udf
def udf():
    return fused.api.list("s3://<BUCKET_NAME>/")
```

Reading and writing S3 files from UDFs works with standard libraries (`boto3`, `s3fs`, `pandas`) once the role is attached — the runtime inherits the IAM permissions automatically.

---

## Airtable

Docs: https://docs.fused.io/workbench/integrations/airtable

All operations go through `fused.api.airtable_connect()`.

### List bases

```python
@fused.udf()
def udf():
    at = fused.api.airtable_connect()
    bases = at.list_bases()
    for base in bases:
        print(base["id"], base["name"])
```

### Read records

```python
@fused.udf()
def udf():
    import pandas as pd
    at = fused.api.airtable_connect(base_id="appXXXXXXXXXXXXXX")
    records = at.list_records(
        "Tasks",
        view="Grid view",
        filterByFormula="{Status} = 'Done'",
        maxRecords=100,
    )
    rows = [{"id": r["id"], **r["fields"]} for r in records]
    return pd.DataFrame(rows)
```

### Create records

```python
@fused.udf()
def udf():
    at = fused.api.airtable_connect(base_id="appXXXXXXXXXXXXXX")
    created = at.create_records("Tasks", [
        {"fields": {"Name": "Buy groceries", "Status": "Todo"}},
        {"fields": {"Name": "Write docs", "Status": "In Progress"}},
    ])
    for r in created:
        print(r["id"])
```

### Update records

```python
@fused.udf()
def udf():
    at = fused.api.airtable_connect(base_id="appXXXXXXXXXXXXXX")
    at.update_records("Tasks", [
        {"id": "recXXXXXXXXXXXXXX", "fields": {"Status": "Done"}},
    ])
```

### Delete records

```python
@fused.udf()
def udf():
    at = fused.api.airtable_connect(base_id="appXXXXXXXXXXXXXX")
    at.delete_records("Tasks", ["recAAAAAAAAAAAA", "recBBBBBBBBBBBB"])
```

**Connection methods:** `.list_bases()`, `.list_records(table, view=, filterByFormula=, maxRecords=)`, `.create_records(table, rows)`, `.update_records(table, rows)`, `.delete_records(table, ids)`

---

## Notion

Docs: https://docs.fused.io/workbench/integrations/notion

All operations go through `fused.api.notion_connect()`, which returns a thin wrapper. Call `.client()` to get a full `notion-client` SDK instance — `nt` itself does not expose search/create/etc. directly.

> **Access grant required.** If you get `APIResponseError: Could not find page`, the Notion integration hasn't been granted access to that page or database. Fix: Workbench → Integrations → Notion → reconnect and grant access to all relevant pages/databases. This is separate from the OAuth connect step.

> **Notion URL parsing.** URLs copied from Notion often include a query string and block anchor: `https://www.notion.so/workspace/Page-abc123?v=uuid&source=copy_link#blockanchor`. The `#blockanchor` is 32 hex chars and will match a page-ID regex if not stripped first. Always clean the URL before extracting the ID:
> ```python
> clean = url.split("#")[0].split("?")[0].rstrip("/")
> slug = clean.split("/")[-1]
> ```

### Search pages

```python
@fused.udf()
def udf():
    nt = fused.api.notion_connect()
    client = nt.client()
    results = client.search(query="Q4 Planning")
    pages = client.search(query="Meeting", filter={"value": "page", "property": "object"})
```

### Get / update a page

```python
@fused.udf()
def udf():
    nt = fused.api.notion_connect()
    client = nt.client()
    page = client.pages.retrieve(page_id="a1b2c3d4-...")
    client.pages.update(
        page_id="your-page-id",
        properties={"Status": {"status": {"name": "Done"}}},
    )
```

### Query a database

> **⚠ `client.databases.query()` is not available in the Fused Notion client.** Calling it raises `AttributeError: 'DatabasesEndpoint' object has no attribute 'query'`. Use `client.search()` with a page filter instead:

```python
@fused.udf()
def udf():
    nt = fused.api.notion_connect()
    client = nt.client()
    # Search within a specific database by filtering on the database ID via parent
    results = client.search(
        query="",
        filter={"property": "object", "value": "page"},
    )
    for r in results.get("results", []):
        # Check parent to scope to a specific database
        if r.get("parent", {}).get("database_id") == "your-database-id":
            print(r["id"], r["properties"])
```

### Create a page in a database

```python
@fused.udf()
def udf():
    nt = fused.api.notion_connect()
    client = nt.client()
    client.pages.create(
        parent={"database_id": "your-database-id"},
        properties={
            "Name": {"title": [{"text": {"content": "Weekly Report"}}]},
            "Status": {"select": {"name": "Draft"}},
        },
    )
```

### Create a page with formatted bullet-point content

Pass `children` as a list of block dicts. Use `bulleted_list_item` blocks (not a single `paragraph` with `\n`) so content renders as actual bullets. Use `annotations` for bold labels:

```python
@fused.udf()
def udf():
    nt = fused.api.notion_connect()
    client = nt.client()

    def bullet(label, text):
        return {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [
                    {"type": "text", "text": {"content": label}, "annotations": {"bold": True}},
                    {"type": "text", "text": {"content": " " + text}},
                ]
            },
        }

    client.pages.create(
        parent={"database_id": "your-database-id"},
        properties={
            "Name": {"title": [{"text": {"content": "My ticket"}}]},
        },
        children=[
            bullet("What:", "The widget fails on empty datasets."),
            bullet("Fix:", "Add a null-check before rendering."),
        ],
    )
```

> **Note:** Putting formatted content in a single `paragraph` block with `\n` separators renders `**bold**` as literal asterisks. Always use separate block types.

### Pull all pages into a DataFrame

```python
@fused.udf()
def udf():
    import pandas as pd
    nt = fused.api.notion_connect()
    client = nt.client()
    response = client.search(filter={"value": "page", "property": "object"})
    rows = []
    for p in response["results"]:
        props = p.get("properties", {})
        title_parts = props.get("Name", {}).get("title", [])
        title = "".join(t["plain_text"] for t in title_parts)
        rows.append({"id": p["id"], "title": title, "url": p.get("url"), "last_edited": p.get("last_edited_time")})
    return pd.DataFrame(rows)
```

### Read a JSON code block from a Notion page

A useful pattern for lightweight data storage: write a JSON code block to a dedicated Notion page (e.g. from a daily pipeline), then read it back in a UDF. This avoids needing file storage for simple structured data.

```python
@fused.udf
def udf():
    import json
    nt = fused.api.notion_connect()
    client = nt.client()
    blocks = client.blocks.children.list(block_id="YOUR_PAGE_ID")
    for block in blocks["results"]:
        if block["type"] == "code":
            raw = block["code"]["rich_text"][0]["plain_text"]
            return json.dumps(json.loads(raw))  # validate + return
    return json.dumps({})
```

To write the code block from a pipeline (e.g. a Claude agent), use `notion-update-page` with `replace_content` and format the JSON inside a fenced ` ```json ``` ` block.

### ⚠ notion_connect() fails in shared URL execution environment

`fused.api.notion_connect()` works correctly when running via `fused workbench run` (local or remote authenticated execution), but **can fail with HTTP 422** when the UDF is called via a public shared URL endpoint (e.g. `https://udf.ai/fc_TOKEN/udf_name`). The Notion OAuth token is not available in that unauthenticated execution context.

**Fix:** wrap in try/except and fall back to an alternative data source (e.g. Fused file storage):

```python
@fused.udf
def udf():
    import json

    # Try Notion first (works in authenticated context)
    try:
        nt = fused.api.notion_connect()
        client = nt.client()
        blocks = client.blocks.children.list(block_id="YOUR_PAGE_ID")
        for block in blocks["results"]:
            if block["type"] == "code":
                raw = block["code"]["rich_text"][0]["plain_text"]
                data = json.loads(raw)
                if data:
                    return json.dumps(data)
    except Exception:
        pass

    # Fall back to Fused file storage (works in all contexts)
    try:
        import fsspec
        with fsspec.open("s3://fused-users/fused/YOUR_USERNAME/data/latest.json", "r") as f:
            return json.dumps(json.load(f))
    except Exception:
        pass

    return json.dumps({})
```

---

## Modal

Docs: https://docs.fused.io/workbench/integrations/modal

Run Modal apps, functions, and serverless GPU workloads. Set `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` in **Settings > Integrations & Secrets**. `fused.api.modal_connect()` returns an authenticated `modal.Client` and configures the SDK for the current process — subsequent `modal.Function.from_name(...).remote(...)` calls authenticate automatically.

### Invoke a deployed function

```python
@fused.udf()
def udf(prompt: str = "A high-resolution satellite image of a coastline"):
    import modal
    fused.api.modal_connect()
    generate = modal.Function.from_name("image-gen", "generate")
    return generate.remote(prompt)
```

### Fan out with `.map()`

```python
@fused.udf()
def udf():
    import modal, pandas as pd
    fused.api.modal_connect()
    embed = modal.Function.from_name("embeddings", "embed")
    texts = ["hello", "world", "fused", "modal"]
    vectors = list(embed.map(texts))
    return pd.DataFrame({"text": texts, "embedding": vectors})
```

### Class-based service

```python
fused.api.modal_connect()
Model = modal.Cls.from_name("llm-app", "Llama")
model = Model()
return model.complete.remote("Explain GeoParquet in one paragraph.")
```

### Async (spawn + poll)

```python
call = train.spawn(epochs=10)
# Later UDF: modal.FunctionCall.from_id(call.object_id).get()
```

---

## Hugging Face

Docs: https://docs.fused.io/workbench/integrations/huggingface

Token stored as `HUGGINGFACE_API_KEY`. Two helpers, both pre-authenticated:

- `fused.api.huggingface_connect()` → `HfApi` (repos, models, datasets, files, Spaces)
- `fused.api.huggingface_inference()` → `InferenceClient` (hosted chat, embeddings, text-to-image, ASR…)

### Inspect / list models

```python
@fused.udf()
def udf():
    import pandas as pd
    hf = fused.api.huggingface_connect()
    models = hf.list_models(author="meta-llama", limit=20)
    return pd.DataFrame([{"id": m.id, "downloads": m.downloads, "likes": m.likes} for m in models])
```

### Download a file from a repo

```python
from huggingface_hub import hf_hub_download
fused.api.huggingface_connect()  # configures token
path = hf_hub_download(repo_id="meta-llama/Llama-3.2-1B-Instruct", filename="config.json")
```

### Load a dataset

```python
from datasets import load_dataset
fused.api.huggingface_connect()
ds = load_dataset("squad", split="validation[:100]")
return ds.to_pandas()
```

### Chat completion (hosted inference)

```python
client = fused.api.huggingface_inference()
reply = client.chat_completion(
    model="meta-llama/Llama-3.2-3B-Instruct",
    messages=[{"role": "user", "content": question}],
    max_tokens=256,
)
return reply.choices[0].message.content
```

### Embeddings

```python
client = fused.api.huggingface_inference()
vec = client.feature_extraction("coastal erosion", model="sentence-transformers/all-MiniLM-L6-v2")
```

### Text-to-image

```python
client = fused.api.huggingface_inference()
image = client.text_to_image(prompt, model="black-forest-labs/FLUX.1-schnell")  # PIL.Image
```

### Push to a repo

```python
hf = fused.api.huggingface_connect()
hf.upload_file(
    path_or_fileobj="results.parquet",
    path_in_repo="results.parquet",
    repo_id="my-org/my-dataset",
    repo_type="dataset",
)
```

---

## Baseten

Docs: https://docs.fused.io/workbench/integrations/baseten

API key stored as `BASETEN_API_KEY`. No connect helper — Baseten exposes an **OpenAI-compatible** endpoint at `https://inference.baseten.co/v1`, so use the `openai` SDK (pre-installed in the runtime).

### Chat completion

```python
@fused.udf()
def udf(prompt: str = "Summarize what GeoParquet is in one sentence."):
    from openai import OpenAI
    client = OpenAI(
        api_key=fused.secrets["BASETEN_API_KEY"],
        base_url="https://inference.baseten.co/v1",
    )
    response = client.chat.completions.create(
        model="deepseek-ai/DeepSeek-V3.1",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=256,
    )
    return response.choices[0].message.content
```

### Streaming

```python
stream = client.chat.completions.create(
    model="deepseek-ai/DeepSeek-V3.1",
    messages=[{"role": "user", "content": "Write a haiku about S3."}],
    stream=True,
)
return "".join(chunk.choices[0].delta.content or "" for chunk in stream)
```

### Dedicated model deployment

For models deployed to your own Baseten workspace, call the model-specific endpoint with an `Api-Key` header:

```python
import requests
api_key = fused.secrets["BASETEN_API_KEY"]
resp = requests.post(
    f"https://model-{model_id}.api.baseten.co/production/predict",
    headers={"Authorization": f"Api-Key {api_key}"},
    json={"prompt": "Hello, world!"},
    timeout=60,
)
resp.raise_for_status()
return resp.json()
```

---

## Daytona

Docs: https://docs.fused.io/workbench/integrations/daytona

Run untrusted code, manage files, and clone repositories in cloud sandboxes. API key stored as `DAYTONA_API_KEY`. `fused.api.daytona_connect()` returns an authenticated `Daytona` client.

> **Always clean up sandboxes.** Wrap usage in `try/finally` with `daytona.delete(sandbox)` — orphaned sandboxes keep running and accrue cost.

### Create a sandbox and run code

```python
@fused.udf()
def udf():
    daytona = fused.api.daytona_connect()
    sandbox = daytona.create()
    try:
        response = sandbox.process.code_run('import math; print(f"{math.pi:.10f}")')
        return response.result
    finally:
        daytona.delete(sandbox)
```

### Stateful execution (variables persist)

```python
sandbox.code_interpreter.run_code("data = [1, 2, 3, 4, 5]")
result = sandbox.code_interpreter.run_code("print(sum(data))")  # 15
```

### Upload / download files

```python
sandbox.fs.upload_file("/home/daytona/input.txt", b"Hello, world!")
content = sandbox.fs.download_file("/home/daytona/input.txt")
```

### Clone a Git repo

```python
sandbox.git.clone(url="https://github.com/fusedio/udfs", path="/home/daytona/udfs")
```

### Custom configuration

```python
from daytona import CreateSandboxFromSnapshotParams
params = CreateSandboxFromSnapshotParams(
    language="python",
    env_vars={"DEBUG": "true"},
    auto_stop_interval=0,
)
sandbox = daytona.create(params, timeout=40)
```

**Client methods:** `.create(params=, timeout=)`, `.get(sandbox_id)`, `.list()`, `.delete(sandbox)`
**Sandbox surfaces:** `.process.code_run(code)`, `.code_interpreter.run_code(code)`, `.fs.upload_file/.download_file`, `.git.clone(url=, path=)`

---

## ComfyOrg (Comfy Cloud)

Docs: https://docs.fused.io/workbench/integrations/comfy

Run [ComfyUI](https://www.comfy.org) workflows on Comfy Cloud. API key stored as `COMFY_API_KEY`. There is **no connect helper** — call the REST API at `https://cloud.comfy.org` directly.

Prerequisite: export your workflow as JSON via **Graph → Export (API)** in ComfyUI and upload it somewhere Fused can read (typically S3).

The flow is: load workflow → patch input nodes → `POST /api/prompt` → poll `/api/job/{id}/status` → download from `/api/view`.

```python
@fused.udf()
def udf(prompt: str = "A high-resolution satellite image of a coastline"):
    import io, time, requests, numpy as np
    from PIL import Image

    BASE_URL = "https://cloud.comfy.org"
    api_key = fused.secrets["COMFY_API_KEY"]
    headers = {"X-API-Key": api_key}

    # 1. Load workflow JSON from S3
    workflow = requests.get(fused.api.sign_url("s3://your-bucket/workflow.json")).json()

    # 2. Patch input nodes — node IDs are top-level keys in the exported JSON
    workflow["104:90"]["inputs"]["text"] = prompt
    workflow["104:92"]["inputs"]["seed"] = 42

    # 3. Submit
    prompt_id = requests.post(
        f"{BASE_URL}/api/prompt",
        headers={**headers, "Content-Type": "application/json"},
        json={"prompt": workflow, "extra_data": {"api_key_comfy_org": api_key}},
    ).json()["prompt_id"]

    # 4. Poll
    history = {}
    for _ in range(120):
        job = requests.get(f"{BASE_URL}/api/job/{prompt_id}/status", headers=headers).json()
        if job.get("status") in ("failed", "cancelled", "error"):
            raise RuntimeError(f"Comfy job failed: {job.get('error_message')}")
        if job.get("status") in ("success", "completed"):
            history = requests.get(f"{BASE_URL}/api/history_v2/{prompt_id}", headers=headers).json().get(prompt_id, {})
            break
        time.sleep(5)

    # 5. Download first output image
    for node_outputs in history.get("outputs", {}).values():
        for file_info in node_outputs.get("images", []):
            data = requests.get(
                f"{BASE_URL}/api/view",
                headers=headers,
                params={"filename": file_info["filename"], "type": file_info.get("type", "output")},
            ).content
            return np.array(Image.open(io.BytesIO(data)))
```

> **Node IDs are workflow-specific.** Keys like `"104:90"` come from one particular exported workflow — open your own JSON and look up the actual top-level keys for the nodes you want to patch.

### Upload an input image

For image-to-video or style-transfer workflows, upload the input first and reference its returned filename:

```python
resp = requests.post(
    f"{BASE_URL}/api/upload/image",
    headers={"X-API-Key": fused.secrets["COMFY_API_KEY"]},
    files={"image": (fname, img_bytes, "image/png")},
)
uploaded_name = resp.json()["name"]
workflow["3"]["inputs"]["image"] = uploaded_name
```

### Cache the slow job, wrap with a thin UDF

Generation is expensive — split the work: a `@fused.cache` helper that submits/polls/uploads to S3, and a thin `@fused.udf(engine="small")` wrapper that returns a `fused.api.sign_url(...)`. `engine="small"` runs as a batch job so you escape the 120-second realtime UDF limit (often necessary for video).

---

## Anthropic

Docs: https://docs.anthropic.com/en/api/client-sdks/python

API key stored as `ANTHROPIC_API_KEY`. `fused.api.anthropic_connect()` returns an authenticated `anthropic.Anthropic` client — the full SDK surface is available (`client.messages`, `client.models`, `client.beta`).

### Chat completion

```python
@fused.udf()
def udf(question: str = "Explain map projections in three sentences."):
    client = fused.api.anthropic_connect()
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": question}],
    )
    return message.content[0].text
```

### System prompt

```python
client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    system="You are a geospatial data expert. Answer concisely.",
    messages=[{"role": "user", "content": question}],
)
```

### Streaming

```python
with client.messages.stream(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Write a Haversine function."}],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
```

### Tool use

```python
tools = [{
    "name": "get_weather",
    "description": "Get the current weather for a location.",
    "input_schema": {
        "type": "object",
        "properties": {"latitude": {"type": "number"}, "longitude": {"type": "number"}},
        "required": ["latitude", "longitude"],
    },
}]
message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "What's the weather in San Francisco?"}],
)
for block in message.content:
    if block.type == "tool_use":
        print(block.name, block.input)
```

### Vision (base64 image)

```python
import base64
with open("satellite.png", "rb") as f:
    image_data = base64.standard_b64encode(f.read()).decode()
client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_data}},
            {"type": "text", "text": "Describe the land use patterns."},
        ],
    }],
)
```

> **Anthropic image format differs from OpenAI.** Anthropic uses `{"type": "image", "source": {"type": "base64", "media_type": ..., "data": ...}}`. OpenAI uses `{"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}`. Don't swap them.

Token usage is on `message.usage.input_tokens` / `message.usage.output_tokens`.

---

## OpenAI

Docs: https://platform.openai.com/docs/libraries/python

API key stored as `OPENAI_API_KEY`. `fused.api.openai_connect()` returns an authenticated `openai.OpenAI` client — the full SDK surface is available (`client.chat.completions`, `client.embeddings`, `client.images`, `client.models`).

### Chat completion

```python
@fused.udf()
def udf(question: str = "Summarize GeoParquet's key features."):
    client = fused.api.openai_connect()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": question}],
    )
    return response.choices[0].message.content
```

### System prompt

```python
client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a geospatial data expert. Answer concisely."},
        {"role": "user", "content": question},
    ],
)
```

### Streaming

```python
stream = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Write a Haversine function."}],
    stream=True,
)
for chunk in stream:
    content = chunk.choices[0].delta.content
    if content:
        print(content, end="", flush=True)
```

### Function calling

```python
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a location.",
        "parameters": {
            "type": "object",
            "properties": {"latitude": {"type": "number"}, "longitude": {"type": "number"}},
            "required": ["latitude", "longitude"],
        },
    },
}]
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What's the weather in San Francisco?"}],
    tools=tools,
)
for tc in response.choices[0].message.tool_calls or []:
    print(tc.function.name, tc.function.arguments)  # arguments is a JSON string — json.loads it
```

### Vision (data URI)

```python
import base64
with open("satellite.png", "rb") as f:
    image_data = base64.standard_b64encode(f.read()).decode()
client.chat.completions.create(
    model="gpt-4o",
    messages=[{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}},
            {"type": "text", "text": "Describe the land use patterns."},
        ],
    }],
)
```

### Embeddings

```python
response = client.embeddings.create(
    model="text-embedding-3-small",
    input=["geospatial data processing", "satellite imagery analysis"],
)
vectors = [d.embedding for d in response.data]
```

Token usage is on `response.usage.prompt_tokens` / `response.usage.completion_tokens` (note: different names than Anthropic).

---

## Slack (Experimental)

Docs: https://docs.fused.io/workbench/integrations/slack

Slack integration is a **team-level Slack bot for talking to a Canvas** — it is not a UDF-level helper. Enable it in **Preferences → Slack integration**, then check the **Integrations** panel on your Fused home page:

- **SYNCED** — your team is set up. Go straight to *Adding a new Canvas to Slack* in the docs.
- **STANDBY** — run the one-time team setup (Loom walkthrough in the docs).

There is no `fused.api.slack_connect()` and no `SLACK_*` secret in UDFs — wiring happens at the team/canvas level, not in code.

---

## Secrets (generic key/value)

Any secret stored via `fused workbench secrets set KEY VALUE` (or the Workbench UI) is available as `fused.secrets["KEY"]` inside any UDF. Use this for API keys, tokens, or JSON credential blobs that don't have a first-class connect helper.

```python
@fused.udf
def udf():
    api_key = fused.secrets["my_api_key"]
```

> **`fused.secrets` raises on missing keys.** Accessing a key that doesn't exist raises `SecretKeyNotFound`, not `KeyError` and not `None`. Run `fused workbench secrets list` to verify a key exists before relying on it in a UDF.
