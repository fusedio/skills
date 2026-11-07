# Querying an indexed dataset over HTTP

`GET /h3/query` returns the rows of an indexed hex dataset as one Parquet file, with no UDF. Use it from a shell, a script or a web page. Inside a UDF, use `fused.h3.query` instead (see [`SKILL.md`](SKILL.md), "Query").

```bash
curl -G "https://www.fused.io/server/v1/h3/query" \
  --data-urlencode "path=s3://fused-asset/data/nyc311/" \
  -d min_lng=-73.99 -d min_lat=40.75 -d max_lng=-73.98 -d max_lat=40.76 \
  -d time_min=2024-07-01 -d time_max=2024-07-01T23:59:59 \
  -d columns=hex -d columns=created_date -d columns=complaint_type \
  -o rows.parquet
```

Then read `rows.parquet` like any Parquet file:

```python
import duckdb
duckdb.sql("SELECT complaint_type, count(*) AS n FROM 'rows.parquet' GROUP BY 1 ORDER BY n DESC")
```

- `path` must be written exactly as it was passed to `fused.h3.index`, trailing slash included or not.
- Give at most one spatial selector (here a bbox). Time bounds only work on a dataset indexed with a time column.
- For your team's datasets, add `-H "Authorization: Bearer $TOKEN"`. Without a token, only a public `s3://` dataset can be read.
- A big result comes back in pages: while the response has an `X-Fused-Next-Cursor` header, repeat the request with `cursor=<that value>`.
- In a browser page, `fetch` the same URL and decode the body with a Parquet reader (hyparquet, parquet-wasm).

Every parameter, the `stats` and `files` formats and the error codes: [H3 query API reference](https://docs.fused.io/rest-api/h3/).
