import argparse
import io
import re
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
from psycopg2 import sql
from psycopg2.extras import Json, execute_values

from src.config import FAILED_DIR, FILE_TABLE_MAP, PROCESSED_DIR, SEED_DIR
from src.ingestion.db import get_conn, init_schema
from src.ingestion.metrics import already_loaded, log_batch, utcnow
from src.ingestion.validators import validate


def resolve_table(filename):
    for prefix, table in FILE_TABLE_MAP:
        if filename.startswith(prefix):
            return table
    return None


def clean_col(c):
    c = re.sub(r"[^0-9a-zA-Z]+", "_", str(c).strip()).strip("_").lower()
    if not c:
        c = "col"
    if c[0].isdigit():
        c = "c_" + c
    return c


def read_file(path):
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    else:
        df = pd.read_excel(path, dtype=str)
    df.columns = [clean_col(c) for c in df.columns]
    return df


def ensure_table(cur, table, cols):
    cur.execute(
        sql.SQL(
            "CREATE TABLE IF NOT EXISTS {} ("
            "_row_id BIGSERIAL PRIMARY KEY, _loaded_at TIMESTAMP, _source_file TEXT)"
        ).format(sql.Identifier(table))
    )
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = %s AND table_schema = current_schema()",
        (table,),
    )
    existing = {r[0] for r in cur.fetchall()}
    for c in cols:
        if c not in existing:  # new table or schema drift
            cur.execute(
                sql.SQL("ALTER TABLE {} ADD COLUMN {} TEXT").format(
                    sql.Identifier(table), sql.Identifier(c)
                )
            )


def copy_df(cur, table, df):
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="")
    buf.seek(0)
    stmt = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv)").format(
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(c) for c in df.columns),
    )
    cur.copy_expert(stmt.as_string(cur), buf)


def insert_rejects(cur, source_file, table, rejects, limit=5000):
    rej = rejects.head(limit)
    cols = [c for c in rej.columns if c != "_reject_reason"]
    data = rej[cols].astype(object).where(rej[cols].notna(), None)
    rows = [
        (source_file, table, reason, Json(rec))
        for reason, rec in zip(rej["_reject_reason"], data.to_dict("records"))
    ]
    execute_values(
        cur,
        "INSERT INTO stg_rejects (source_file, target_table, reject_reason, raw_row) VALUES %s",
        rows,
    )


def _move(path, dest_dir):
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    if dest.exists():
        dest = dest_dir / f"{path.stem}_{datetime.now():%H%M%S}{path.suffix}"
    shutil.move(str(path), str(dest))


def load_file(path, move=True, detected_at=None):
    path = Path(path)
    name = path.name

    if already_loaded(name):
        print(f"[skip]   {name} already loaded")
        if move:
            _move(path, PROCESSED_DIR)
        return

    started = utcnow()
    file_size_mb = round(path.stat().st_size / (1024 * 1024), 3)
    table, rows_read, rows_loaded, rows_rejected = None, 0, 0, 0
    try:
        table = resolve_table(name)
        if table is None:
            raise ValueError(f"No staging table mapped for file '{name}' (prefix not 01_/05_/06_)")

        df = read_file(path)
        rows_read = len(df)
        clean, rejects = validate(df, table)
        rows_loaded, rows_rejected = len(clean), len(rejects)

        clean["_loaded_at"] = started
        clean["_source_file"] = name

        conn = get_conn()
        try:
            with conn, conn.cursor() as cur:   # one transaction: all or nothing
                ensure_table(cur, table, clean.columns)
                if rows_loaded:
                    copy_df(cur, table, clean)
                if rows_rejected:
                    insert_rejects(cur, name, table, rejects)
        finally:
            conn.close()

        dur = log_batch(name, table, started, "success", rows_read, rows_loaded,
                        rows_rejected, file_size_mb=file_size_mb, detected_at=detected_at)
        print(f"[ok]     {name} -> {table} | {file_size_mb} MB | read={rows_read} "
              f"loaded={rows_loaded} rejected={rows_rejected} | {dur:.2f}s")
        if move:
            _move(path, PROCESSED_DIR)

    except Exception as e:
        log_batch(name, table, started, "failed", rows_read, 0, 0, str(e)[:1000],
                  file_size_mb=file_size_mb, detected_at=detected_at)
        print(f"[FAILED] {name}: {e}")
        if move and path.exists():
            _move(path, FAILED_DIR)


def load_seed():
    init_schema()
    for f in sorted(SEED_DIR.glob("*.csv")):
        if resolve_table(f.name):
            load_file(f, move=False)   # seed files stay where they are


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="load the original CSVs from data/seed")
    ap.add_argument("--file", help="load one specific file")
    args = ap.parse_args()
    if args.seed:
        load_seed()
    elif args.file:
        init_schema()
        load_file(args.file, move=False)
    else:
        ap.print_help()