-- Rebuilt after every transform run. DuckDB has no materialized views,
-- so these tables play that role (grain: month x medicine x channel / month x medicine).
CREATE OR REPLACE TABLE agg_sales_monthly AS
SELECT d.year_month,
       m.medicine_id,
       m.generic_name,
       m.therapeutic_class,
       j.sales_channel,
       SUM(f.quantity_sold_packs)    AS units_sold,
       SUM(f.returned_quantity_packs) AS returned_units,
       SUM(f.gross_sales_amount_usd) AS gross_sales_usd,
       SUM(f.discount_amount_usd)    AS discount_usd,
       SUM(f.net_sales_amount_usd)   AS net_sales_usd,
       SUM(f.cost_of_goods_sold_usd) AS cogs_usd,
       SUM(f.gross_margin_usd)       AS gross_margin_usd,
       SUM(f.sales_tax_usd)          AS tax_usd,
       COUNT(*)                      AS transactions
FROM fact_pharmacy_sales f
JOIN dim_sales_date d ON d.date_key = f.sales_date_key
JOIN dim_medicine m   ON m.medicine_key = f.medicine_key
JOIN dim_sales_junk j ON j.sales_junk_key = f.sales_junk_key
GROUP BY ALL;

CREATE OR REPLACE TABLE agg_demand_monthly AS
SELECT d.year_month,
       m.medicine_id,
       m.therapeutic_class,
       SUM(f.forecast_demand_packs)    AS forecast_packs,
       SUM(f.requested_quantity_packs) AS requested_packs,
       SUM(f.consumed_quantity_packs)  AS consumed_packs,
       SUM(f.unfulfilled_demand_packs) AS unfulfilled_packs,
       SUM(f.wastage_quantity_packs)   AS wastage_packs,
       SUM(f.stockout_days)            AS stockout_days,
       COUNT(*)                        AS records
FROM fact_hospital_demand f
JOIN dim_demand_month d ON d.date_key = f.demand_month_key
JOIN dim_medicine m     ON m.medicine_key = f.medicine_key
GROUP BY ALL;