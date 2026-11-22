import json
import re
import uuid
from datetime import datetime, timezone

import pandas as pd

from src.config import DATA_DIR, LANDING_DIR, SEED_DIR

STATE_FILE = DATA_DIR / "generator_state.json"
LOG_FILE = DATA_DIR / "oversampling_log.csv"      # evidence for the oversampling PDF
DATE_FORMATS = ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"]


def read_seed(prefix):
    path = next(SEED_DIR.glob(f"{prefix}*.csv"))
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def load_state():
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def next_ids(state, key, existing, n):
    """n new IDs continuing the numeric suffix of the existing ones (e.g. ...000500001)."""
    m = re.match(r"^(.*?)(\d+)$", existing.iloc[0])
    if not m:   # no numeric suffix: fall back to random unique IDs
        return [f"G{uuid.uuid4().hex[:12].upper()}" for _ in range(n)]
    prefix, width = m.group(1), len(m.group(2))
    biggest = pd.to_numeric(existing.str.extract(r"(\d+)$")[0], errors="coerce").max()
    start = int(max(state.get(key, 0), biggest)) + 1
    state[key] = start + n - 1
    return [f"{prefix}{i:0{width}d}" for i in range(start, start + n)]


def detect_format(values):
    sample = [v for v in values.head(2000) if v]
    for fmt in DATE_FORMATS:
        try:
            for v in sample:
                datetime.strptime(v, fmt)
            print(f"[info] date format detected: {fmt}  (e.g. {sample[0]})")
            return fmt
        except ValueError:
            continue
    raise ValueError(f"Unknown date format. First values: {sample[:3]}")


def fmt_num(series, decimals):
    return series.map(lambda v: "" if pd.isna(v) else f"{v:.{decimals}f}")


def write_landing(df, stem):
    """Write .tmp then rename, so the watcher/DAG only ever sees finished files."""
    LANDING_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{stem}_{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.csv"
    tmp = LANDING_DIR / (name + ".tmp")
    df.to_csv(tmp, index=False)
    final = LANDING_DIR / name
    tmp.replace(final)
    return final


def log_batch(path, rows, first_id, last_id, min_date, max_date):
    pd.DataFrame([{
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "file": path.name, "rows": rows, "first_id": first_id, "last_id": last_id,
        "min_date": min_date, "max_date": max_date,
    }]).to_csv(LOG_FILE, mode="a", header=not LOG_FILE.exists(), index=False)