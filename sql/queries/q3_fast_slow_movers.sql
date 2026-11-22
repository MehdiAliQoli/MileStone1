-- Q3: Fast vs slow moving medicines (velocity quartiles + cumulative share)
WITH per_med AS (
    SELECT m.medicine_id,
           ANY_VALUE(m.generic_name)      AS generic_name,
           ANY_VALUE(m.therapeutic_class) AS therapeutic_class,
           SUM(f.quantity_sold_packs)     AS units_sold,
           SUM(f.net_sales_amount_usd)    AS net_sales_usd,
           COUNT(DISTINCT d.year_month)   AS active_months
    FROM fact_pharmacy_sales f
    JOIN dim_medicine m   ON m.medicine_key = f.medicine_key
    JOIN dim_sales_date d ON d.date_key = f.sales_date_key
    GROUP BY m.medicine_id
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