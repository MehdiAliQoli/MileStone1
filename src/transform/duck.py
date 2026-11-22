import io

import duckdb
import pandas as pd
import psycopg2

from src.config import BASE_DIR, DUCKDB_PATH, PG

# staging table -> temp table holding only the NEW rows (since last watermark)
SLICES = {
    "stg_master": "new_master",
    "stg_warehouse": "new_warehouse",
    "stg_sales": "new_sales",
    "stg_hospital_demand": "new_demand",
}


def connect(read_only=False):
    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DUCKDB_PATH), read_only=read_only)


def pg_scalar(sql):
    """Run a single-value query against Postgres staging."""
    conn = psycopg2.connect(**PG)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone()[0]
    finally:
        conn.close()


def run_sql_file(con, relpath):
    con.execute((BASE_DIR / relpath).read_text())


def _fetch_slice(table, last_row_id):
    """Pull staging rows with _row_id > last_row_id into a DataFrame (all text)."""
    conn = psycopg2.connect(**PG)
    buf = io.StringIO()
    try:
        with conn.cursor() as cur:
            cur.copy_expert(
                f"COPY (SELECT * FROM {table} WHERE _row_id > {int(last_row_id)} "
                f"ORDER BY _row_id) TO STDOUT WITH (FORMAT csv, HEADER true)", buf)
    finally:
        conn.close()
    buf.seek(0)
    df = pd.read_csv(buf, dtype=str, keep_default_na=False, na_values=[""])
    return df.astype(object).where(df.notna(), None)


def stage_slices(con):
    wm = dict(con.execute("SELECT source_table, last_row_id FROM etl_watermark").fetchall())
    counts = {}
    for stg, tmp in SLICES.items():
        df = _fetch_slice(stg, wm.get(stg, 0))
        con.register("df_slice", df)
        cols = [c for c in df.columns if c != "_row_id"]
        select = ", ".join(f'CAST("{c}" AS VARCHAR) AS "{c}"' for c in cols)
        con.execute(f"CREATE OR REPLACE TEMP TABLE {tmp} AS "
                    f"SELECT {select}, CAST(_row_id AS BIGINT) AS _row_id FROM df_slice")
        con.unregister("df_slice")
        counts[stg] = len(df)
    return counts


def advance_watermarks(con):
    for stg, tmp in SLICES.items():
        mx = con.execute(f"SELECT max(_row_id) FROM {tmp}").fetchone()[0]
        if mx is not None:
            con.execute("INSERT OR REPLACE INTO etl_watermark VALUES (?, ?)", [stg, int(mx)])