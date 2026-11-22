from src.transform.scd import load_dim_medicine


def _count(con, t):
    return con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]


def load_dim_pharmacy(con):
    before = _count(con, "dim_pharmacy")
    con.execute("""
        CREATE OR REPLACE TEMP TABLE src_pharmacy AS
        SELECT pharmacyid AS pharmacy_id, pharmacygln AS pharmacy_gln, pharmacyname AS pharmacy_name,
               pharmacytype AS pharmacy_type, pharmacycity AS pharmacy_city,
               pharmacystate AS pharmacy_state, countrycode AS country_code, hospitalid AS hospital_id
        FROM new_sales WHERE pharmacyid IS NOT NULL
        QUALIFY row_number() OVER (PARTITION BY pharmacyid ORDER BY _row_id DESC) = 1
    """)
    con.execute("""
        UPDATE dim_pharmacy d SET pharmacy_gln = s.pharmacy_gln, pharmacy_name = s.pharmacy_name,
            pharmacy_type = s.pharmacy_type, pharmacy_city = s.pharmacy_city,
            pharmacy_state = s.pharmacy_state, country_code = s.country_code, hospital_id = s.hospital_id
        FROM src_pharmacy s WHERE d.pharmacy_id = s.pharmacy_id
    """)
    con.execute("""
        INSERT INTO dim_pharmacy (pharmacy_id, pharmacy_gln, pharmacy_name, pharmacy_type,
                                  pharmacy_city, pharmacy_state, country_code, hospital_id)
        SELECT s.pharmacy_id, s.pharmacy_gln, s.pharmacy_name, s.pharmacy_type, s.pharmacy_city,
               s.pharmacy_state, s.country_code, s.hospital_id
        FROM src_pharmacy s
        WHERE NOT EXISTS (SELECT 1 FROM dim_pharmacy d WHERE d.pharmacy_id = s.pharmacy_id)
    """)
    return _count(con, "dim_pharmacy") - before


def load_dim_hospital(con):
    before = _count(con, "dim_hospital")
    con.execute("""
        CREATE OR REPLACE TEMP TABLE src_hospital AS
        SELECT hospitalid AS hospital_id, hospitalgln AS hospital_gln, hospitalname AS hospital_name,
               hospitaltype AS hospital_type, hospitalpharmacyid AS hospital_pharmacy_id,
               city, state, countrycode AS country_code,
               m_int(licensedbeds) AS licensed_beds, m_int(icubeds) AS icu_beds,
               tramalevel_placeholder AS trauma_level,
               m_int(catchmentpopulation) AS catchment_population,
               m_num(averageoccupancyratepct) AS average_occupancy_rate_pct
        FROM new_demand WHERE hospitalid IS NOT NULL
        QUALIFY row_number() OVER (PARTITION BY hospitalid ORDER BY _row_id DESC) = 1
    """.replace("tramalevel_placeholder", "traumalevel"))
    con.execute("""
        UPDATE dim_hospital d SET hospital_gln = s.hospital_gln, hospital_name = s.hospital_name,
            hospital_type = s.hospital_type, hospital_pharmacy_id = s.hospital_pharmacy_id,
            city = s.city, state = s.state, country_code = s.country_code,
            licensed_beds = s.licensed_beds, icu_beds = s.icu_beds, trauma_level = s.trauma_level,
            catchment_population = s.catchment_population,
            average_occupancy_rate_pct = s.average_occupancy_rate_pct
        FROM src_hospital s WHERE d.hospital_id = s.hospital_id
    """)
    con.execute("""
        INSERT INTO dim_hospital (hospital_id, hospital_gln, hospital_name, hospital_type,
            hospital_pharmacy_id, city, state, country_code, licensed_beds, icu_beds,
            trauma_level, catchment_population, average_occupancy_rate_pct)
        SELECT s.hospital_id, s.hospital_gln, s.hospital_name, s.hospital_type,
               s.hospital_pharmacy_id, s.city, s.state, s.country_code, s.licensed_beds,
               s.icu_beds, s.trauma_level, s.catchment_population, s.average_occupancy_rate_pct
        FROM src_hospital s
        WHERE NOT EXISTS (SELECT 1 FROM dim_hospital d WHERE d.hospital_id = s.hospital_id)
    """)
    return _count(con, "dim_hospital") - before


def load_dim_warehouse_lot(con):
    before = _count(con, "dim_warehouse_lot")
    # real lots from file 04 (latest snapshot per lot)
    con.execute("""
        CREATE OR REPLACE TEMP TABLE src_lot AS
        SELECT warehouselotid AS warehouse_lot_id, warehouseid AS warehouse_id,
               warehousename AS warehouse_name, storagezoneid AS storage_zone_id,
               storagecondition AS storage_condition, productionbatchid AS production_batch_id,
               m_date(batchexpirydate) AS batch_expiry_date,
               m_flag(nearexpiryflag) AS near_expiry_flag,
               m_flag(fefocomplianceflag) AS fefo_compliance_flag
        FROM new_warehouse WHERE warehouselotid IS NOT NULL
        QUALIFY row_number() OVER (PARTITION BY warehouselotid ORDER BY _row_id DESC) = 1
    """)
    con.execute("""
        UPDATE dim_warehouse_lot d SET warehouse_id = s.warehouse_id, warehouse_name = s.warehouse_name,
            storage_zone_id = s.storage_zone_id, storage_condition = s.storage_condition,
            production_batch_id = s.production_batch_id, batch_expiry_date = s.batch_expiry_date,
            near_expiry_flag = s.near_expiry_flag, fefo_compliance_flag = s.fefo_compliance_flag,
            is_inferred = false
        FROM src_lot s WHERE d.warehouse_lot_id = s.warehouse_lot_id
    """)
    con.execute("""
        INSERT INTO dim_warehouse_lot (warehouse_lot_id, warehouse_id, warehouse_name, storage_zone_id,
            storage_condition, production_batch_id, batch_expiry_date, near_expiry_flag,
            fefo_compliance_flag, is_inferred)
        SELECT s.warehouse_lot_id, s.warehouse_id, s.warehouse_name, s.storage_zone_id,
               s.storage_condition, s.production_batch_id, s.batch_expiry_date,
               s.near_expiry_flag, s.fefo_compliance_flag, false
        FROM src_lot s
        WHERE NOT EXISTS (SELECT 1 FROM dim_warehouse_lot d WHERE d.warehouse_lot_id = s.warehouse_lot_id)
    """)
    # inferred members: lots referenced by sales but missing from dim
    con.execute("""
        INSERT INTO dim_warehouse_lot (warehouse_lot_id, production_batch_id, is_inferred)
        SELECT warehouselotid, any_value(productionbatchid), true
        FROM new_sales
        WHERE warehouselotid IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM dim_warehouse_lot d WHERE d.warehouse_lot_id = new_sales.warehouselotid)
        GROUP BY warehouselotid
    """)
    return _count(con, "dim_warehouse_lot") - before


def load_dim_sales_junk(con):
    before = _count(con, "dim_sales_junk")
    con.execute("""
        INSERT INTO dim_sales_junk (sales_channel, payment_method, payer_type, customer_segment, promotion_code)
        SELECT c.* FROM (
            SELECT DISTINCT COALESCE(saleschannel, 'Unknown'), COALESCE(paymentmethod, 'Unknown'),
                   COALESCE(payertype, 'Unknown'), COALESCE(customersegment, 'Unknown'),
                   COALESCE(promotioncode, 'Unknown')
            FROM new_sales) AS c(ch, pm, pt, cs, pc)
        WHERE NOT EXISTS (SELECT 1 FROM dim_sales_junk j
                          WHERE j.sales_channel = c.ch AND j.payment_method = c.pm
                            AND j.payer_type = c.pt AND j.customer_segment = c.cs
                            AND j.promotion_code = c.pc)
    """)
    return _count(con, "dim_sales_junk") - before


# (step name, function). Dimensions always load before facts.
DIM_STEPS = [
    ("dim_medicine (SCD2)", load_dim_medicine),
    ("dim_pharmacy", load_dim_pharmacy),
    ("dim_hospital", load_dim_hospital),
    ("dim_warehouse_lot", load_dim_warehouse_lot),
    ("dim_sales_junk", load_dim_sales_junk),
]