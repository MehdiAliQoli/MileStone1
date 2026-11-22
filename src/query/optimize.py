import argparse
import shutil
import statistics

from src.config import WAREHOUSE_DIR
from src.query.run_query import run_and_log
from src.transform.duck import connect, run_sql_file

INDEXES = [
    ("idx_sales_date",      "fact_pharmacy_sales",  "sales_date_key"),
    ("idx_sales_medicine",  "fact_pharmacy_sales",  "medicine_key"),
    ("idx_sales_junk",      "fact_pharmacy_sales",  "sales_junk_key"),
    ("idx_demand_month",    "fact_hospital_demand", "demand_month_key"),
    ("idx_demand_medicine", "fact_hospital_demand", "medicine_key"),
]

PARQUET_DIR = WAREHOUSE_DIR / "parquet" / "fact_sales"


def create_indexes(con):
    for name, table, col in INDEXES:
        con.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({col})")
    print(f"created {len(INDEXES)} indexes")


def drop_indexes(con):
    for name, _, _ in INDEXES:
        con.execute(f"DROP INDEX IF EXISTS {name}")
    print("dropped indexes")


def refresh_summaries(con):
    """Rebuild summary tables. Airflow runs this after every transform."""
    run_sql_file(con, "sql/summary/create_summaries.sql")
    for t in ("agg_sales_monthly", "agg_demand_monthly"):
        print(f"{t}: {con.execute(f'SELECT count(*) FROM {t}').fetchone()[0]} rows")


def export_partitioned_parquet(con):
    """Write fact sales to Parquet partitioned by year/month. Returns the POSIX path."""
    # DuckDB creates only the last folder, not its parents, so create
    # warehouse/parquet first (this was the "path not found" error on Windows).
    PARQUET_DIR.parent.mkdir(parents=True, exist_ok=True)

    # Start clean so a rerun never leaves stale partitions from older data.
    if PARQUET_DIR.exists():
        shutil.rmtree(PARQUET_DIR, ignore_errors=True)

    path = PARQUET_DIR.as_posix()
    con.execute(f"""
        COPY (SELECT f.*, d.cal_year, d.cal_month
              FROM fact_pharmacy_sales f
              JOIN dim_date d ON d.date_key = f.sales_date_key)
        TO '{path}' (FORMAT PARQUET, PARTITION_BY (cal_year, cal_month), OVERWRITE_OR_IGNORE true)
    """)
    n_files = sum(1 for _ in PARQUET_DIR.rglob("*.parquet"))
    print(f"exported partitioned Parquet: {n_files} files in {path}")
    return path


def partition_benchmark(con, repeat=5):
    """Partitioned Parquet (year/month) vs the single DuckDB table, for a one-month query."""
    path = export_partitioned_parquet(con)

    y, m = con.execute(
        "SELECT cal_year, cal_month FROM dim_date "
        "WHERE date_key = (SELECT max(sales_date_key) FROM fact_pharmacy_sales)").fetchone()
    print(f"benchmarking month {y}-{m:02d}")

    variants = {
        "single_table": f"""
            SELECT sum(f.net_sales_amount_usd), count(*) FROM fact_pharmacy_sales f
            JOIN dim_date d ON d.date_key = f.sales_date_key
            WHERE d.cal_year = {y} AND d.cal_month = {m}""",
        "partitioned_parquet": f"""
            SELECT sum(net_sales_amount_usd), count(*)
            FROM read_parquet('{path}/**/*.parquet', hive_partitioning = true)
            WHERE cal_year = {y} AND cal_month = {m}""",
    }
    for variant, sql in variants.items():
        con.execute(sql).fetchall()   # warm-up (not logged)
        times = [run_and_log(con, "q5_single_month_revenue", variant, sql)[0]
                 for _ in range(repeat)]
        print(f"q5_single_month_revenue {variant:<20} "
              f"median={statistics.median(times):.1f} ms   min={min(times):.1f} ms")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--indexes", action="store_true")
    ap.add_argument("--drop-indexes", action="store_true")
    ap.add_argument("--summaries", action="store_true")
    ap.add_argument("--partition", action="store_true")
    args = ap.parse_args()

    con = connect()
    try:
        if args.indexes:
            create_indexes(con)
        if args.drop_indexes:
            drop_indexes(con)
        if args.summaries:
            refresh_summaries(con)
        if args.partition:
            partition_benchmark(con)
    finally:
        con.close()