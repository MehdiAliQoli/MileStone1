from src.transform.duck import connect, pg_scalar

# (name, DuckDB query on the mart, Postgres query on staging) - results must match
CHECKS = [
    ("sales rows = distinct txn IDs in staging",
     "SELECT count(*) FROM fact_pharmacy_sales",
     "SELECT count(DISTINCT salestransactionid) FROM stg_sales"),
    ("demand rows = distinct record IDs in staging",
     "SELECT count(*) FROM fact_hospital_demand",
     "SELECT count(DISTINCT hospitaldemandrecordid) FROM stg_hospital_demand"),
    ("net sales total: fact = staging",
     "SELECT round(sum(net_sales_amount_usd), 2) FROM fact_pharmacy_sales",
     "SELECT round(sum(CASE WHEN netsalesamountusd ~ '^-?[0-9]+(\\.[0-9]+)?$' "
     "THEN netsalesamountusd::numeric END), 2) FROM stg_sales"),
    ("current medicines = distinct medicine IDs",
     "SELECT count(*) FROM dim_medicine WHERE is_current AND medicine_key <> -1",
     "SELECT count(DISTINCT medicineid) FROM stg_master"),
]

ORPHANS = {   # these should all be 0
    "sales: unknown date":      "SELECT count(*) FROM fact_pharmacy_sales WHERE sales_date_key = -1",
    "sales: unknown medicine":  "SELECT count(*) FROM fact_pharmacy_sales WHERE medicine_key = -1",
    "sales: unknown pharmacy":  "SELECT count(*) FROM fact_pharmacy_sales WHERE pharmacy_key = -1",
    "sales: unknown lot":       "SELECT count(*) FROM fact_pharmacy_sales WHERE warehouse_lot_key = -1",
    "sales: unknown junk":      "SELECT count(*) FROM fact_pharmacy_sales WHERE sales_junk_key = -1",
    "demand: unknown month":    "SELECT count(*) FROM fact_hospital_demand WHERE demand_month_key = -1",
    "demand: unknown hospital": "SELECT count(*) FROM fact_hospital_demand WHERE hospital_key = -1",
    "demand: unknown medicine": "SELECT count(*) FROM fact_hospital_demand WHERE medicine_key = -1",
    "sales: null net sales":    "SELECT count(*) FROM fact_pharmacy_sales WHERE net_sales_amount_usd IS NULL",
    "lots inferred (not in 04)": "SELECT count(*) FROM dim_warehouse_lot WHERE is_inferred",
}


def main():
    con = connect()
    print("== reconciliation")
    for name, duck_sql, pg_sql in CHECKS:
        a = con.execute(duck_sql).fetchone()[0]
        b = pg_scalar(pg_sql)
        ok = abs(float(a or 0) - float(b or 0)) < 0.01
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: mart={a} source={b}")
    print("== orphans / quality (expect 0)")
    for name, sql in ORPHANS.items():
        n = con.execute(sql).fetchone()[0]
        print(f"[{'OK  ' if n == 0 else 'LOOK'}] {name}: {n}")
    print("== table sizes")
    for t in ("dim_date", "dim_medicine", "dim_pharmacy", "dim_hospital", "dim_warehouse_lot",
              "dim_sales_junk", "fact_pharmacy_sales", "fact_hospital_demand"):
        print(f"{t}: {con.execute(f'SELECT count(*) FROM {t}').fetchone()[0]}")
    con.close()


if __name__ == "__main__":
    main()