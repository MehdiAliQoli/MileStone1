-- Q4: Multi-fact drill-across: retail sales vs hospital demand by class and month
WITH s AS (
    SELECT d.year_month, m.therapeutic_class,
           SUM(f.quantity_sold_packs)  AS units_sold,
           SUM(f.net_sales_amount_usd) AS net_sales_usd
    FROM fact_pharmacy_sales f
    JOIN dim_sales_date d ON d.date_key = f.sales_date_key
    JOIN dim_medicine m   ON m.medicine_key = f.medicine_key
    GROUP BY d.year_month, m.therapeutic_class
), h AS (
    SELECT d.year_month, m.therapeutic_class,
           SUM(f.requested_quantity_packs)  AS requested_packs,
           SUM(f.unfulfilled_demand_packs)  AS unfulfilled_packs
    FROM fact_hospital_demand f
    JOIN dim_demand_month d ON d.date_key = f.demand_month_key
    JOIN dim_medicine m     ON m.medicine_key = f.medicine_key
    GROUP BY d.year_month, m.therapeutic_class
)
SELECT year_month, therapeutic_class, units_sold, net_sales_usd, requested_packs, unfulfilled_packs
FROM s FULL OUTER JOIN h USING (year_month, therapeutic_class)
ORDER BY year_month, therapeutic_class;