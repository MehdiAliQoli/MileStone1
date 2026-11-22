-- Q2: Revenue and margin by sales channel and month
SELECT d.year_month,
       j.sales_channel,
       SUM(f.net_sales_amount_usd)   AS net_sales_usd,
       SUM(f.cost_of_goods_sold_usd) AS cogs_usd,
       SUM(f.gross_margin_usd)       AS gross_margin_usd,
       ROUND(100.0 * SUM(f.gross_margin_usd) / NULLIF(SUM(f.net_sales_amount_usd), 0), 2) AS margin_pct,
       SUM(f.quantity_sold_packs)    AS units_sold,
       COUNT(*)                      AS transactions,
       ROUND(100.0 * SUM(f.returned_quantity_packs) / NULLIF(SUM(f.quantity_sold_packs), 0), 2) AS return_rate_pct
FROM fact_pharmacy_sales f
JOIN dim_sales_date d  ON d.date_key = f.sales_date_key
JOIN dim_sales_junk j  ON j.sales_junk_key = f.sales_junk_key
GROUP BY d.year_month, j.sales_channel
ORDER BY d.year_month, j.sales_channel;