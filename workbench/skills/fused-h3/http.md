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
- The host is your environment's server; `https://www.fused.io/server/v1` is production. Inside a UDF, it is `fused.options.base_url`.
- Give at most one spatial selector (here a bbox). Time bounds only work on a dataset indexed with a time column.
- HTTP also takes a polygon selector, which `fused.h3.query` does not: `polygon` (GeoJSON `Polygon` or `MultiPolygon`, as a JSON string) or `polygon_wkt` (WKT). `contain` (`center`, the default, `full` or `overlap`) picks which cells a bbox or polygon keeps, and `k` (0 to 25) adds every cell within `k` steps. A polygon too long for a URL goes in a JSON body to `POST /h3/query`, with the same parameter names.
- For your team's datasets, add `-H "Authorization: Bearer $TOKEN"` (inside a UDF, the token is `fused.api.access_token()`). Without a token, only a public `s3://` dataset can be read; anything else is a 403.
- A big result comes back in pages: while the response has an `X-Fused-Next-Cursor` header, repeat the request with `cursor=<that value>`. `max_row_groups` (1 to 4,096, default 1,024) sets the page size.
- In a browser page, `fetch` the same URL and decode the body with a Parquet reader (hyparquet, parquet-wasm).

Every parameter, the `files` format and the error codes: [H3 query API reference](https://docs.fused.io/rest-api/h3/).
