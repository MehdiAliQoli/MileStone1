SALES_SQL = """
INSERT OR IGNORE INTO fact_pharmacy_sales (
    sales_transaction_id, sales_date_key, medicine_key, pharmacy_key, warehouse_lot_key,
    sales_junk_key, production_batch_id, quantity_sold_packs, gross_sales_amount_usd,
    discount_amount_usd, net_sales_amount_usd, cost_of_goods_sold_usd, gross_margin_usd,
    sales_tax_usd, returned_quantity_packs, days_to_expiry_at_sale, delivery_otif_flag,
    return_flag, src_row_id)
SELECT s.salestransactionid,
       m_dkey(s.sale_date),
       COALESCE(m.medicine_key, -1),
       COALESCE(p.pharmacy_key, -1),
       COALESCE(w.warehouse_lot_key, -1),
       COALESCE(j.sales_junk_key, -1),
       s.productionbatchid,
       m_int(s.quantitysoldpacks), m_num(s.grosssalesamountusd), m_num(s.discountamountusd),
       m_num(s.netsalesamountusd), m_num(s.costofgoodssoldusd), m_num(s.grossmarginusd),
       m_num(s.salestaxusd), m_int(s.returnedquantitypacks), m_int(s.daystoexpiryatsale),
       m_flag(s.deliveryotifflag), m_flag(s.returnflag), s._row_id
FROM (SELECT *, m_date(salesdate) AS sale_date
      FROM new_sales WHERE salestransactionid IS NOT NULL) s
LEFT JOIN dim_medicine m
       ON m.medicine_id = s.medicineid
      AND COALESCE(s.sale_date, CURRENT_DATE) BETWEEN m.valid_from AND m.valid_to
LEFT JOIN dim_pharmacy p       ON p.pharmacy_id = s.pharmacyid
LEFT JOIN dim_warehouse_lot w  ON w.warehouse_lot_id = s.warehouselotid
LEFT JOIN dim_sales_junk j
       ON j.sales_channel = COALESCE(s.saleschannel, 'Unknown')
      AND j.payment_method = COALESCE(s.paymentmethod, 'Unknown')
      AND j.payer_type = COALESCE(s.payertype, 'Unknown')
      AND j.customer_segment = COALESCE(s.customersegment, 'Unknown')
      AND j.promotion_code = COALESCE(s.promotioncode, 'Unknown')
"""

DEMAND_SQL = """
INSERT OR IGNORE INTO fact_hospital_demand (
    hospital_demand_record_id, demand_month_key, hospital_key, medicine_key,
    forecast_demand_packs, requested_quantity_packs, approved_quantity_packs,
    received_quantity_packs, emergency_request_quantity_packs, dispensed_quantity_packs,
    consumed_quantity_packs, wastage_quantity_packs, opening_stock_packs, closing_stock_packs,
    unfulfilled_demand_packs, stockout_days, service_level_pct, estimated_disease_cases,
    demand_trend_index, average_lead_time_days, src_row_id)
SELECT d.hospitaldemandrecordid,
       m_dkey(d.month_start),
       COALESCE(h.hospital_key, -1),
       COALESCE(m.medicine_key, -1),
       m_int(d.forecastdemandpacks), m_int(d.requestedquantitypacks), m_int(d.approvedquantitypacks),
       m_int(d.receivedquantitypacks), m_int(d.emergencyrequestquantitypacks),
       m_int(d.dispensedquantitypacks), m_int(d.consumedquantitypacks), m_int(d.wastagequantitypacks),
       m_int(d.openingstockpacks), m_int(d.closingstockpacks), m_int(d.unfulfilleddemandpacks),
       m_int(d.stockoutdays), m_num(d.servicelevelpct), m_int(d.estimateddiseasecases),
       m_num(d.demandtrendindex), m_num(d.averageleadtimedays), d._row_id
FROM (SELECT *, CAST(date_trunc('month', m_date(demandmonth)) AS DATE) AS month_start
      FROM new_demand WHERE hospitaldemandrecordid IS NOT NULL) d
LEFT JOIN dim_hospital h ON h.hospital_id = d.hospitalid
LEFT JOIN dim_medicine m
       ON m.medicine_id = d.medicineid
      AND COALESCE(d.month_start, CURRENT_DATE) BETWEEN m.valid_from AND m.valid_to
"""


def _load(con, table, sql):
    before = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    con.execute(sql)
    return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0] - before


def load_fact_sales(con):
    return _load(con, "fact_pharmacy_sales", SALES_SQL)


def load_fact_demand(con):
    return _load(con, "fact_hospital_demand", DEMAND_SQL)


FACT_STEPS = [
    ("fact_pharmacy_sales", load_fact_sales),
    ("fact_hospital_demand", load_fact_demand),
]