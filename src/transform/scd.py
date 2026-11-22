def _count(con, t):
    return con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]


def load_dim_medicine(con):
    """SCD Type 2 on price, cost and status. Returns number of new versions created."""
    con.execute("""
        CREATE OR REPLACE TEMP TABLE src_med AS
        SELECT *,
               md5(concat_ws('|',
                   COALESCE(CAST(wholesale_price_usd AS VARCHAR), '~'),
                   COALESCE(CAST(recommended_retail_price_usd AS VARCHAR), '~'),
                   COALESCE(CAST(unit_manufacturing_cost_usd AS VARCHAR), '~'),
                   COALESCE(product_status, '~'))) AS row_hash
        FROM (
            SELECT medicineid AS medicine_id, gtin14, genericname AS generic_name,
                   fictionalbrandname AS brand_name, diseasecategory AS disease_category,
                   icd10category AS icd10_category, atccode AS atc_code,
                   therapeuticclass AS therapeutic_class, dosageform AS dosage_form,
                   strength, routeofadministration AS route_of_administration,
                   packsize AS pack_size, prescriptionclass AS prescription_class,
                   m_flag(controlledmedicineflag) AS controlled_medicine_flag,
                   m_flag(coldchainflag) AS cold_chain_flag,
                   m_int(shelflifemonths) AS shelf_life_months,
                   m_num(wholesalepriceusd) AS wholesale_price_usd,
                   m_num(recommendedretailpriceusd) AS recommended_retail_price_usd,
                   m_num(unitmanufacturingcostusd) AS unit_manufacturing_cost_usd,
                   productstatus AS product_status
            FROM new_master
            WHERE medicineid IS NOT NULL
            QUALIFY row_number() OVER (PARTITION BY medicineid ORDER BY _row_id DESC) = 1
        )
    """)
    before = _count(con, "dim_medicine")

    # 1) close the current version of rows whose tracked attributes changed
    con.execute("""
        UPDATE dim_medicine d
        SET valid_to = CURRENT_DATE - 1, is_current = false
        FROM src_med s
        WHERE d.medicine_id = s.medicine_id AND d.is_current AND d.row_hash <> s.row_hash
    """)

    # 2) insert new medicines and new versions of changed ones
    con.execute("""
        INSERT INTO dim_medicine (
            medicine_id, gtin14, generic_name, brand_name, disease_category, icd10_category,
            atc_code, therapeutic_class, dosage_form, strength, route_of_administration,
            pack_size, prescription_class, controlled_medicine_flag, cold_chain_flag,
            shelf_life_months, wholesale_price_usd, recommended_retail_price_usd,
            unit_manufacturing_cost_usd, product_status, row_hash,
            valid_from, valid_to, is_current)
        SELECT s.medicine_id, s.gtin14, s.generic_name, s.brand_name, s.disease_category,
               s.icd10_category, s.atc_code, s.therapeutic_class, s.dosage_form, s.strength,
               s.route_of_administration, s.pack_size, s.prescription_class,
               s.controlled_medicine_flag, s.cold_chain_flag, s.shelf_life_months,
               s.wholesale_price_usd, s.recommended_retail_price_usd,
               s.unit_manufacturing_cost_usd, s.product_status, s.row_hash,
               CASE WHEN EXISTS (SELECT 1 FROM dim_medicine o WHERE o.medicine_id = s.medicine_id)
                    THEN CURRENT_DATE ELSE DATE '1900-01-01' END,
               DATE '9999-12-31', true
        FROM src_med s
        WHERE NOT EXISTS (SELECT 1 FROM dim_medicine d
                          WHERE d.medicine_id = s.medicine_id AND d.is_current)
    """)
    return _count(con, "dim_medicine") - before