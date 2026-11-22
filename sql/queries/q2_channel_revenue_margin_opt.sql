SELECT year_month,
       sales_channel,
       SUM(net_sales_usd)    AS net_sales_usd,
       SUM(cogs_usd)         AS cogs_usd,
       SUM(gross_margin_usd) AS gross_margin_usd,
       ROUND(100.0 * SUM(gross_margin_usd) / NULLIF(SUM(net_sales_usd), 0), 2) AS margin_pct,
       SUM(units_sold)       AS units_sold,
       SUM(transactions)     AS transactions,
       ROUND(100.0 * SUM(returned_units) / NULLIF(SUM(units_sold), 0), 2) AS return_rate_pct
FROM agg_sales_monthly
GROUP BY year_month, sales_channel
ORDER BY year_month, sales_channel;