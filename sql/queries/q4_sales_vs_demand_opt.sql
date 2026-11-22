WITH s AS (
    SELECT year_month, therapeutic_class,
           SUM(units_sold) AS units_sold, SUM(net_sales_usd) AS net_sales_usd
    FROM agg_sales_monthly GROUP BY year_month, therapeutic_class
), h AS (
    SELECT year_month, therapeutic_class,
           SUM(requested_packs) AS requested_packs, SUM(unfulfilled_packs) AS unfulfilled_packs
    FROM agg_demand_monthly GROUP BY year_month, therapeutic_class
)
SELECT year_month, therapeutic_class, units_sold, net_sales_usd, requested_packs, unfulfilled_packs
FROM s FULL OUTER JOIN h USING (year_month, therapeutic_class)
ORDER BY year_month, therapeutic_class;