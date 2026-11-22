import psycopg2

from src.config import DUCKDB_PATH, FAILED_DIR, LANDING_DIR, PG, PROCESSED_DIR
from src.ingestion.metrics import utcnow
from src.transform.duck import connect

STAGING = ["stg_master", "stg_sales", "stg_hospital_demand", "stg_rejects", "load_log", "query_log"]
MART = ["dim_date", "dim_medicine", "dim_pharmacy", "dim_hospital", "dim_warehouse_lot",
        "dim_sales_junk", "fact_pharmacy_sales", "fact_hospital_demand",
        "agg_sales_monthly", "agg_demand_monthly"]
FACT_DATE_KEY = {"fact_pharmacy_sales": "sales_date_key", "fact_hospital_demand": "demand_month_key"}

DDL = """
CREATE TABLE IF NOT EXISTS storage_stats (
    stat_id BIGSERIAL PRIMARY KEY, captured_at TIMESTAMP NOT NULL,
    layer TEXT NOT NULL, object_name TEXT NOT NULL,
    row_count BIGINT, size_mb DOUBLE PRECISION, min_date DATE, max_date DATE);
CREATE OR REPLACE VIEW v_storage_latest AS
SELECT DISTINCT ON (layer, object_name) layer, object_name, row_count, size_mb,
       min_date, max_date, captured_at
FROM storage_stats ORDER BY layer, object_name, captured_at DESC;
"""


def _dir_stats(d):
    files = [f for f in d.glob("*") if f.is_file() and not f.name.startswith(".")]
    return len(files), round(sum(f.stat().st_size for f in files) / 1048576, 2)


def snapshot():
    now, rows = utcnow(), []

    con = connect(read_only=True)
    try:
        for t in MART:
            try:
                n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            except Exception:
                continue                      # table doesn't exist yet
            lo = hi = None
            if t in FACT_DATE_KEY:
                k = FACT_DATE_KEY[t]
                lo, hi = con.execute(
                    f"SELECT min(d.full_date), max(d.full_date) FROM {t} f "
                    f"JOIN dim_date d ON d.date_key = f.{k} WHERE f.{k} <> -1").fetchone()
            rows.append(("mart", t, n, None, lo, hi))
    finally:
        con.close()

    size = round(DUCKDB_PATH.stat().st_size / 1048576, 2) if DUCKDB_PATH.exists() else None
    rows.append(("warehouse", "sdi_mart.duckdb", None, size, None, None))

    for label, d in (("landing", LANDING_DIR), ("processed", PROCESSED_DIR), ("failed", FAILED_DIR)):
        n, mb = _dir_stats(d)
        rows.append(("files", label, n, mb, None, None))

    conn = psycopg2.connect(**PG)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(DDL)
            for t in STAGING:
                cur.execute("SELECT to_regclass(%s)", (t,))
                if cur.fetchone()[0] is None:
                    continue
                cur.execute(f"SELECT count(*), pg_total_relation_size('{t}') FROM {t}")
                n, b = cur.fetchone()
                rows.append(("staging", t, n, round(b / 1048576, 2), None, None))
            for r in rows:
                cur.execute(
                    "INSERT INTO storage_stats (captured_at, layer, object_name, row_count, "
                    "size_mb, min_date, max_date) VALUES (%s,%s,%s,%s,%s,%s,%s)", (now, *r))
    finally:
        conn.close()
    print(f"storage snapshot saved: {len(rows)} rows")


if __name__ == "__main__":
    snapshot()