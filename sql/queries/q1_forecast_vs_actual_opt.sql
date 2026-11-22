SELECT year_month,
       therapeutic_class,
       SUM(forecast_packs)  AS forecast_packs,
       SUM(requested_packs) AS actual_demand_packs,
       SUM(forecast_packs) - SUM(requested_packs) AS forecast_error_packs,
       ROUND(100.0 * (SUM(forecast_packs) - SUM(requested_packs))
             / NULLIF(SUM(requested_packs), 0), 2) AS forecast_error_pct,
       ROUND(100.0 * SUM(unfulfilled_packs)
             / NULLIF(SUM(requested_packs), 0), 2) AS unfulfilled_pct
FROM agg_demand_monthly
GROUP BY year_month, therapeutic_class
ORDER BY year_month, therapeutic_class;