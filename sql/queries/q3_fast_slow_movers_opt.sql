WITH per_med AS (
    SELECT medicine_id,
           ANY_VALUE(generic_name)      AS generic_name,
           ANY_VALUE(therapeutic_class) AS therapeutic_class,
           SUM(units_sold)              AS units_sold,
           SUM(net_sales_usd)           AS net_sales_usd,
           COUNT(DISTINCT year_month)   AS active_months
    FROM agg_sales_monthly
    GROUP BY medicine_id
), ranked AS (
    SELECT *,
           NTILE(4) OVER (ORDER BY units_sold DESC, medicine_id) AS velocity_quartile,
           SUM(units_sold) OVER (ORDER BY units_sold DESC, medicine_id) * 1.0
               / SUM(units_sold) OVER () AS cum_share
    FROM per_med
)
SELECT medicine_id, generic_name, therapeutic_class, units_sold, net_sales_usd, active_months,
       ROUND(100 * cum_share, 1) AS cum_units_pct,
       CASE velocity_quartile WHEN 1 THEN 'Fast mover'
                              WHEN 4 THEN 'Slow mover'
                              ELSE 'Medium' END AS movement_class
FROM ranked
ORDER BY units_sold DESC, medicine_id;