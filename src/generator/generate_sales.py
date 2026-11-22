import argparse

import numpy as np
import pandas as pd

from src.generator import common as c

MONEY_COLS = ["GrossSalesAmountUSD", "DiscountAmountUSD", "NetSalesAmountUSD",
              "CostOfGoodsSoldUSD", "GrossMarginUSD", "SalesTaxUSD"]


def generate(rows=50_000, window_days=30, seed=None):
    rng = np.random.default_rng(seed)
    src = c.read_seed("05_")
    state = c.load_state()

    fmt = c.detect_format(src["SalesDate"])
    seed_max = pd.to_datetime(src["SalesDate"], format=fmt, errors="coerce").max()
    last = pd.Timestamp(state.get("sales_last_date", seed_max))

    out = src.sample(n=rows, replace=True,
                     random_state=int(rng.integers(10**9))).reset_index(drop=True)
    out["SalesTransactionID"] = c.next_ids(state, "sales_id", src["SalesTransactionID"], rows)

    # new transactions arrive AFTER the latest date already loaded
    dates = last + pd.to_timedelta(rng.integers(1, window_days + 1, rows), unit="D")
    out["SalesDate"] = dates.strftime(fmt)

    # quantity +-20%, amounts scale with it, so unit prices stay realistic
    q = pd.to_numeric(out["QuantitySoldPacks"], errors="coerce")
    q_new = (q * rng.uniform(0.8, 1.2, rows)).round().clip(lower=1)
    ratio = (q_new / q).where(q > 0, 1.0)
    out["QuantitySoldPacks"] = c.fmt_num(q_new, 0)
    for col in MONEY_COLS:
        out[col] = c.fmt_num(pd.to_numeric(out[col], errors="coerce") * ratio, 2)
    ret = pd.to_numeric(out["ReturnedQuantityPacks"], errors="coerce")
    out["ReturnedQuantityPacks"] = c.fmt_num(np.minimum(ret, q_new), 0)

    path = c.write_landing(out, "05_pharmacy_sales_gen")
    state["sales_last_date"] = dates.max().strftime("%Y-%m-%d")
    c.save_state(state)
    ids = out["SalesTransactionID"]
    c.log_batch(path, rows, ids.iloc[0], ids.iloc[-1], dates.min().date(), dates.max().date())
    print(f"[generated] {path.name}: {rows} rows, {dates.min().date()} to {dates.max().date()}")
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=50_000)
    ap.add_argument("--window-days", type=int, default=30)
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    generate(a.rows, a.window_days, a.seed)