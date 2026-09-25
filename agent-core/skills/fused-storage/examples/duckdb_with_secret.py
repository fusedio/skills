# Connect to a Postgres database using a secret stored in Secrets Manager,
# run a query with DuckDB's postgres scanner, and write results to S3.
#
# Store the connection string first (secret name must start with function prefix):
#   fused secrets put openfused-pg-conn      # prompts for the value, no echo
#   (or pipe it: printf '%s' "$PG_CONN" | fused secrets put openfused-pg-conn --value-file -)
#
# Requirements come from the resolved environment, not per-call flags:
#   fused env update <env> -p duckdb -p duckdb-postgres -p pandas -p pyarrow
#
# Usage:
#   fused code run examples/duckdb_with_secret.py

import io

import boto3
import duckdb

BUCKET = "my-bucket"
OUTPUT_KEY = "outputs/pg_export.parquet"
SECRET_NAME = "openfused-pg-conn"

# Retrieve the connection string from Secrets Manager — never put it in the code string
sm = boto3.client("secretsmanager")
pg_conn = sm.get_secret_value(SecretId=SECRET_NAME)["SecretString"]

con = duckdb.connect()
con.execute("INSTALL postgres; LOAD postgres;")
con.execute(f"ATTACH '{pg_conn}' AS pg (TYPE postgres, READ_ONLY)")

df = con.execute("""
    SELECT
        DATE_TRUNC('month', created_at) AS month,
        status,
        COUNT(*)                         AS num_records
    FROM pg.public.orders
    GROUP BY month, status
    ORDER BY month DESC, status
""").df()

out_buf = io.BytesIO()
df.to_parquet(out_buf, index=False)
out_buf.seek(0)

s3 = boto3.client("s3")
s3.put_object(Bucket=BUCKET, Key=OUTPUT_KEY, Body=out_buf.read())

result = f"exported {len(df)} rows → s3://{BUCKET}/{OUTPUT_KEY}"
