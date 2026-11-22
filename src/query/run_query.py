import argparse
import statistics
import time
from decimal import Decimal
from pathlib import Path

from src.config import BASE_DIR
from src.query.logger import log_query
from src.transform.duck import connect

QUERY_DIR = BASE_DIR / "sql" / "queries"


def query_files(opt):
    files = sorted(QUERY_DIR.glob("q[0-9]*.sql"))
    return [f for f in files if f.stem.endswith("_opt") == opt]


def qname(f):
    return f.stem.removesuffix("_opt")


def run_and_log(con, name, variant, sql):
    """Time one execution (including fetching all rows) and log it to Postgres."""
    t0 = time.perf_counter()
    try:
        rows = con.execute(sql).fetchall()
        ms = (time.perf_counter() - t0) * 1000
        log_query(name, variant, ms, len(rows), "success")
        return ms, rows
    except Exception as e:
        ms = (time.perf_counter() - t0) * 1000
        log_query(name, variant, ms, 0, "failed", str(e)[:500])
        print(f"[FAILED] {name}: {e}")
        return ms, None


def benchmark(con, files, variant, repeat):
    for f in files:
        sql = f.read_text()
        try:
            con.execute(sql).fetchall()      # warm-up run (not logged)
        except Exception:
            pass
        times, n = [], 0
        for _ in range(repeat):
            ms, rows = run_and_log(con, qname(f), variant, sql)
            if rows is None:
                break
            times.append(ms)
            n = len(rows)
        if times:
            print(f"{qname(f):<32} {variant:<10} rows={n:<5} "
                  f"median={statistics.median(times):8.1f} ms   min={min(times):8.1f} ms")


def _close(x, y):
    nums = (int, float, Decimal)
    if isinstance(x, nums) and isinstance(y, nums):
        return abs(float(x) - float(y)) <= 0.011
    return x == y


def verify(con):
    """Base and optimized versions must return the same rows."""
    opt = {qname(f): f for f in query_files(True)}
    for bf in query_files(False):
        of = opt.get(qname(bf))
        if not of:
            print(f"[skip]  {qname(bf)}: no _opt version")
            continue
        a = con.execute(bf.read_text()).fetchall()
        b = con.execute(of.read_text()).fetchall()
        same = len(a) == len(b) and all(
            all(_close(x, y) for x, y in zip(r1, r2)) for r1, r2 in zip(a, b))
        print(f"[{'MATCH' if same else 'MISMATCH'}] {qname(bf)} ({len(a)} vs {len(b)} rows)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="run all q*.sql queries")
    ap.add_argument("--opt", action="store_true", help="use the *_opt.sql versions")
    ap.add_argument("--file", help="run one specific query file")
    ap.add_argument("--variant", default="baseline")
    ap.add_argument("--repeat", type=int, default=5)
    ap.add_argument("--verify", action="store_true", help="check base == optimized results")
    args = ap.parse_args()

    con = connect(read_only=True)
    if args.verify:
        verify(con)
    elif args.file:
        p = Path(args.file)
        benchmark(con, [p], args.variant, 1)
    elif args.all:
        benchmark(con, query_files(args.opt), args.variant, args.repeat)
    else:
        ap.print_help()
    con.close()