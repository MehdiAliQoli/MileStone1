-- ===== Helper macros: staging is all TEXT, so every load casts safely =====
CREATE OR REPLACE MACRO m_date(x) AS
    COALESCE(CAST(TRY_CAST(x AS TIMESTAMP) AS DATE),
             CAST(TRY_STRPTIME(x || '-01', '%Y-%m-%d') AS DATE));
CREATE OR REPLACE MACRO m_num(x)  AS TRY_CAST(x AS DECIMAL(18,4));
CREATE OR REPLACE MACRO m_int(x)  AS CAST(ROUND(TRY_CAST(x AS DOUBLE)) AS BIGINT);
CREATE OR REPLACE MACRO m_flag(x) AS
    CASE WHEN upper(trim(x)) IN ('1','Y','YES','TRUE','T') THEN 1
         WHEN upper(trim(x)) IN ('0','N','NO','FALSE','F')  THEN 0 END;
CREATE OR REPLACE MACRO m_dkey(d) AS COALESCE(CAST(strftime(d, '%Y%m%d') AS INTEGER), -1);

-- ===== Sequences (surrogate keys) =====
CREATE SEQUENCE IF NOT EXISTS seq_medicine;
CREATE SEQUENCE IF NOT EXISTS seq_pharmacy;
CREATE SEQUENCE IF NOT EXISTS seq_hospital;
CREATE SEQUENCE IF NOT EXISTS seq_warehouse_lot;
CREATE SEQUENCE IF NOT EXISTS seq_sales_junk;

-- ===== dim_date (role-playing: sales date, demand month) =====
CREATE TABLE IF NOT EXISTS dim_date (
    date_key      INTEGER PRIMARY KEY,      -- yyyymmdd
    full_date     DATE,
    cal_year      INTEGER,
    cal_quarter   INTEGER,
    cal_month     INTEGER,
    month_name    VARCHAR,
    year_month    VARCHAR,
    week_number   INTEGER,
    day_of_month  INTEGER,
    day_of_week   INTEGER,                  -- 1=Mon .. 7=Sun
    day_name      VARCHAR,
    is_weekend    BOOLEAN
);

INSERT OR IGNORE INTO dim_date
SELECT CAST(strftime(d, '%Y%m%d') AS INTEGER), d, year(d), quarter(d), month(d),
       monthname(d), strftime(d, '%Y-%m'), weekofyear(d), day(d), isodow(d),
       dayname(d), isodow(d) >= 6
FROM (SELECT CAST(g AS DATE) AS d
      FROM generate_series(DATE '2015-01-01', DATE '2035-12-31', INTERVAL 1 DAY) AS t(g));

INSERT OR IGNORE INTO dim_date VALUES
    (-1, NULL, NULL, NULL, NULL, 'Unknown', 'Unknown', NULL, NULL, NULL, 'Unknown', NULL);

-- ===== dim_medicine (SCD Type 2) =====
CREATE TABLE IF NOT EXISTS dim_medicine (
    medicine_key                  INTEGER PRIMARY KEY DEFAULT nextval('seq_medicine'),
    medicine_id                   VARCHAR NOT NULL,
    gtin14                        VARCHAR,
    generic_name                  VARCHAR,
    brand_name                    VARCHAR,
    disease_category              VARCHAR,
    icd10_category                VARCHAR,
    atc_code                      VARCHAR,
    therapeutic_class             VARCHAR,
    dosage_form                   VARCHAR,
    strength                      VARCHAR,
    route_of_administration       VARCHAR,
    pack_size                     VARCHAR,
    prescription_class            VARCHAR,
    controlled_medicine_flag      TINYINT,
    cold_chain_flag               TINYINT,
    shelf_life_months             INTEGER,
    wholesale_price_usd           DECIMAL(18,4),   -- tracked (SCD2)
    recommended_retail_price_usd  DECIMAL(18,4),   -- tracked (SCD2)
    unit_manufacturing_cost_usd   DECIMAL(18,4),   -- tracked (SCD2)
    product_status                VARCHAR,         -- tracked (SCD2)
    row_hash                      VARCHAR,
    valid_from                    DATE,
    valid_to                      DATE,
    is_current                    BOOLEAN
);
INSERT OR IGNORE INTO dim_medicine (medicine_key, medicine_id, generic_name, valid_from, valid_to, is_current)
VALUES (-1, 'UNKNOWN', 'Unknown', DATE '1900-01-01', DATE '9999-12-31', true);

-- ===== dim_pharmacy (Type 1) =====
CREATE TABLE IF NOT EXISTS dim_pharmacy (
    pharmacy_key    INTEGER PRIMARY KEY DEFAULT nextval('seq_pharmacy'),
    pharmacy_id     VARCHAR NOT NULL,
    pharmacy_gln    VARCHAR,
    pharmacy_name   VARCHAR,
    pharmacy_type   VARCHAR,
    pharmacy_city   VARCHAR,
    pharmacy_state  VARCHAR,
    country_code    VARCHAR,
    hospital_id     VARCHAR
);
INSERT OR IGNORE INTO dim_pharmacy (pharmacy_key, pharmacy_id, pharmacy_name) VALUES (-1, 'UNKNOWN', 'Unknown');

-- ===== dim_hospital (Type 1) =====
CREATE TABLE IF NOT EXISTS dim_hospital (
    hospital_key               INTEGER PRIMARY KEY DEFAULT nextval('seq_hospital'),
    hospital_id                VARCHAR NOT NULL,
    hospital_gln               VARCHAR,
    hospital_name              VARCHAR,
    hospital_type              VARCHAR,
    hospital_pharmacy_id       VARCHAR,
    city                       VARCHAR,
    state                      VARCHAR,
    country_code               VARCHAR,
    licensed_beds              INTEGER,
    icu_beds                   INTEGER,
    trauma_level               VARCHAR,
    catchment_population       BIGINT,
    average_occupancy_rate_pct DECIMAL(18,4)
);
INSERT OR IGNORE INTO dim_hospital (hospital_key, hospital_id, hospital_name) VALUES (-1, 'UNKNOWN', 'Unknown');

-- ===== dim_warehouse_lot (outrigger / mini-dimension) =====
CREATE TABLE IF NOT EXISTS dim_warehouse_lot (
    warehouse_lot_key     INTEGER PRIMARY KEY DEFAULT nextval('seq_warehouse_lot'),
    warehouse_lot_id      VARCHAR NOT NULL,
    warehouse_id          VARCHAR,
    warehouse_name        VARCHAR,
    storage_zone_id       VARCHAR,
    storage_condition     VARCHAR,
    production_batch_id   VARCHAR,
    batch_expiry_date     DATE,
    near_expiry_flag      TINYINT,      -- value from latest snapshot
    fefo_compliance_flag  TINYINT,      -- value from latest snapshot
    is_inferred           BOOLEAN DEFAULT false   -- true = lot seen in sales but not in file 04
);
INSERT OR IGNORE INTO dim_warehouse_lot (warehouse_lot_key, warehouse_lot_id, warehouse_name, is_inferred)
VALUES (-1, 'UNKNOWN', 'Unknown', false);

-- ===== dim_sales_junk (junk dimension) =====
CREATE TABLE IF NOT EXISTS dim_sales_junk (
    sales_junk_key    INTEGER PRIMARY KEY DEFAULT nextval('seq_sales_junk'),
    sales_channel     VARCHAR,
    payment_method    VARCHAR,
    payer_type        VARCHAR,
    customer_segment  VARCHAR,
    promotion_code    VARCHAR
);
INSERT OR IGNORE INTO dim_sales_junk (sales_junk_key, sales_channel, payment_method, payer_type, customer_segment, promotion_code)
VALUES (-1, 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown');