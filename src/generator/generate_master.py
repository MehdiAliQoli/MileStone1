import argparse

import pandas as pd

from src.generator import common as c


def generate(count=3, pct=0.05):
    out = c.read_seed("01_").sample(n=count).copy()
    for col in ["WholesalePriceUSD", "RecommendedRetailPriceUSD"]:
        out[col] = c.fmt_num(pd.to_numeric(out[col], errors="coerce") * (1 + pct), 2)
    path = c.write_landing(out, "01_master_gen")
    print(f"[generated] {path.name}: {count} price changes")
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3)
    a = ap.parse_args()
    generate(a.count)