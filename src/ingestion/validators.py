import warnings
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

# Exact (cleaned, lowercase) column names that must not be null, per table
NOT_NULL = {
    "stg_master": ["medicineid", "medicine_id", "sku", "sku_id", "skuid"],
    "stg_sales": ["medicineid", "medicine_id", "sku", "sku_id", "skuid"],
    "stg_hospital_demand": ["medicineid", "medicine_id", "sku", "sku_id", "skuid"],
}
# Any column whose name contains one of these gets the check
PRICE_PATTERN = "price"   # must be > 0
DATE_PATTERN = "date"     # must parse as a date


def _parse_dates(s):
    d = pd.to_datetime(s, errors="coerce")
    retry = s.notna() & d.isna()
    if retry.any():
        d[retry] = pd.to_datetime(s[retry], errors="coerce", format="mixed")
    return d


def validate(df, table):
    """Returns (clean_df, rejects_df). rejects_df has a _reject_reason column."""
    reasons = pd.Series([""] * len(df), index=df.index, dtype=object)

    def flag(mask, msg):
        reasons.loc[mask] = reasons.loc[mask] + msg + "; "

    # 1) non-null key columns
    for col in df.columns:
        if col in NOT_NULL.get(table, []):
            flag(df[col].isna() | (df[col].str.strip() == ""), f"{col} is null")

    # 2) price > 0 (only on columns that are mostly numeric)
    for col in df.columns:
        if PRICE_PATTERN in col:
            num = pd.to_numeric(df[col], errors="coerce")
            nonnull = df[col].notna()
            if nonnull.any() and num[nonnull].notna().mean() > 0.5:
                flag(num.isna() | (num <= 0), f"{col} must be > 0")

    # 3) valid dates (only on columns that are mostly parseable)
    for col in df.columns:
        if DATE_PATTERN in col:
            nonnull = df[col].notna()
            if not nonnull.any():
                continue
            d = _parse_dates(df[col])
            if d[nonnull].notna().mean() > 0.5:
                flag(nonnull & d.isna(), f"{col} invalid date")

    bad = reasons != ""
    clean = df.loc[~bad].copy()
    rejects = df.loc[bad].copy()
    rejects["_reject_reason"] = reasons[bad]
    return clean, rejects