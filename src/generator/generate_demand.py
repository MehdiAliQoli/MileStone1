import argparse

import numpy as np
import pandas as pd

from src.generator import common as c


def generate(rows=None, seed=None):
    rng = np.random.default_rng(seed)
    src = c.read_seed("06_")
    state = c.load_state()

    fmt = c.detect_format(src["DemandMonth"])
    seed_last = pd.to_datetime(src["DemandMonth"], format=fmt, errors="coerce").max()
    last = pd.Timestamp(state.get("demand_last_month", seed_last))
    new_month = (last.to_period("M") + 1).to_timestamp()           # next month, day 1

    pairs = src.drop_duplicates(["HospitalID", "MedicineID"])      # grain: hospital x medicine x month
    n = min(rows or len(pairs), len(pairs))
    out = pairs.sample(n=n, random_state=int(rng.integers(10**9))).reset_index(drop=True)
    out["HospitalDemandRecordID"] = c.next_ids(state, "demand_id", src["HospitalDemandRecordID"], n)
    out["DemandMonth"] = new_month.strftime(fmt)

    f = rng.uniform(0.85, 1.15, n)
    for col in [x for x in out.columns if x.endswith("Packs")] + ["EstimatedDiseaseCases"]:
        if col in out:
            out[col] = c.fmt_num(pd.to_numeric(out[col], errors="coerce") * f, 0)

    path = c.write_landing(out, "06_hospital_demand_gen")
    state["demand_last_month"] = new_month.strftime("%Y-%m-%d")
    c.save_state(state)
    ids = out["HospitalDemandRecordID"]
    c.log_batch(path, n, ids.iloc[0], ids.iloc[-1], new_month.date(), new_month.date())
    print(f"[generated] {path.name}: {n} rows for {new_month:%Y-%m}")
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int)
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    generate(a.rows, a.seed)