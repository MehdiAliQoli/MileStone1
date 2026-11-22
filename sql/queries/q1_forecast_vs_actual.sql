-- Q1: Forecast vs actual hospital demand by therapeutic class and month
-- Assumption: "actual demand" = requested quantity
SELECT d.year_month,
       m.therapeutic_class,
       SUM(f.forecast_demand_packs)    AS forecast_packs,
       SUM(f.requested_quantity_packs) AS actual_demand_packs,
       SUM(f.forecast_demand_packs) - SUM(f.requested_quantity_packs) AS forecast_error_packs,
       ROUND(100.0 * (SUM(f.forecast_demand_packs) - SUM(f.requested_quantity_packs))
             / NULLIF(SUM(f.requested_quantity_packs), 0), 2) AS forecast_error_pct,
       ROUND(100.0 * SUM(f.unfulfilled_demand_packs)
             / NULLIF(SUM(f.requested_quantity_packs), 0), 2) AS unfulfilled_pct
FROM fact_hospital_demand f
JOIN dim_demand_month d ON d.date_key = f.demand_month_key
JOIN dim_medicine m     ON m.medicine_key = f.medicine_key
GROUP BY d.year_month, m.therapeutic_class
ORDER BY d.year_month, m.therapeutic_class;