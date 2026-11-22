from datetime import datetime

from src.transform.build_dims import DIM_STEPS
from src.transform.build_facts import FACT_STEPS
from src.transform.duck import advance_watermarks, connect, run_sql_file, stage_slices

SCHEMA_FILES = [
    "sql/mart/create_control.sql",
    "sql/mart/create_dims.sql",
    "sql/mart/create_facts.sql",
]


def run():
    con = connect()
    log = []   # (step, started, ended, rows, status, error)

    def timed(name, fn):
        t0 = datetime.now()
        try:
            rows = fn(con)
            log.append((name, t0, datetime.now(), rows, "success", None))
            print(f"[ok]     {name}: +{rows} rows")
        except Exception as e:
            log.append((name, t0, datetime.now(), 0, "failed", str(e)[:500]))
            print(f"[FAILED] {name}: {e}")
            raise

    try:
        for f in SCHEMA_FILES:
            run_sql_file(con, f)                   # idempotent
        counts = stage_slices(con)
        print("new staging rows to process:", counts)

        con.execute("BEGIN")
        try:
            for name, fn in DIM_STEPS + FACT_STEPS:
                timed(name, fn)
            advance_watermarks(con)
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    finally:
        for step, t0, t1, rows, status, err in log:
            con.execute(
                "INSERT INTO transform_log (step, started_at, ended_at, duration_sec, "
                "rows_affected, status, error_message) VALUES (?,?,?,?,?,?,?)",
                [step, t0, t1, (t1 - t0).total_seconds(), rows, status, err])
        con.close()


if __name__ == "__main__":
    run()