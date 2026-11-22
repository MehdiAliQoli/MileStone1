-- ===== Fact 1: transaction fact. Grain = 1 sales transaction =====
CREATE TABLE IF NOT EXISTS fact_pharmacy_sales (
    sales_transaction_id     VARCHAR PRIMARY KEY,     -- degenerate key
    sales_date_key           INTEGER NOT NULL,        -- -> dim_date (role: sales date)
    medicine_key             INTEGER NOT NULL,        -- -> dim_medicine (as of sale date)
    pharmacy_key             INTEGER NOT NULL,
    warehouse_lot_key        INTEGER NOT NULL,
    sales_junk_key           INTEGER NOT NULL,
    production_batch_id      VARCHAR,                 -- degenerate (no DimBatch in Phase 1)
    quantity_sold_packs      BIGINT,
    gross_sales_amount_usd   DECIMAL(18,4),
    discount_amount_usd      DECIMAL(18,4),
    net_sales_amount_usd     DECIMAL(18,4),
    cost_of_goods_sold_usd   DECIMAL(18,4),
    gross_margin_usd         DECIMAL(18,4),
    sales_tax_usd            DECIMAL(18,4),
    returned_quantity_packs  BIGINT,
    days_to_expiry_at_sale   BIGINT,
    delivery_otif_flag       TINYINT,
    return_flag              TINYINT,
    src_row_id               BIGINT,                  -- staging _row_id (lineage)
    loaded_at                TIMESTAMP DEFAULT current_timestamp
);

-- ===== Fact 2: periodic snapshot. Grain = hospital x medicine x month =====
CREATE TABLE IF NOT EXISTS fact_hospital_demand (
    hospital_demand_record_id        VARCHAR PRIMARY KEY,
    demand_month_key                 INTEGER NOT NULL,   -- -> dim_date (role: demand month, 1st of month)
    hospital_key                     INTEGER NOT NULL,
    medicine_key                     INTEGER NOT NULL,
    forecast_demand_packs            BIGINT,
    requested_quantity_packs         BIGINT,
    approved_quantity_packs          BIGINT,
    received_quantity_packs          BIGINT,
    emergency_request_quantity_packs BIGINT,
    dispensed_quantity_packs         BIGINT,
    consumed_quantity_packs          BIGINT,
    wastage_quantity_packs           BIGINT,
    opening_stock_packs              BIGINT,
    closing_stock_packs              BIGINT,
    unfulfilled_demand_packs         BIGINT,
    stockout_days                    BIGINT,
    service_level_pct                DECIMAL(18,4),
    estimated_disease_cases          BIGINT,
    demand_trend_index               DECIMAL(18,4),
    average_lead_time_days           DECIMAL(18,4),
    src_row_id                       BIGINT,
    loaded_at                        TIMESTAMP DEFAULT current_timestamp
);

-- ===== Role-playing views over dim_date =====
CREATE OR REPLACE VIEW dim_sales_date    AS SELECT * FROM dim_date;
CREATE OR REPLACE VIEW dim_demand_month  AS SELECT * FROM dim_date;