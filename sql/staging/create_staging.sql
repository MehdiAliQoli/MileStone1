-- ============ TABLES ============
CREATE TABLE IF NOT EXISTS load_log (
    load_id               BIGSERIAL PRIMARY KEY,
    source_file           TEXT NOT NULL,
    target_table          TEXT,
    started_at            TIMESTAMP NOT NULL,   -- UTC
    ended_at              TIMESTAMP,            -- UTC
    duration_sec          DOUBLE PRECISION,
    rows_read             INTEGER,
    rows_loaded           INTEGER,
    rows_rejected         INTEGER,
    status                TEXT NOT NULL,        -- 'success' | 'failed'
    error_message         TEXT,
    file_size_mb          DOUBLE PRECISION,
    detected_at           TIMESTAMP,            -- when the watcher saw the file (UTC)
    ingestion_latency_sec DOUBLE PRECISION      -- started_at - detected_at
);

-- for databases created before these columns existed
ALTER TABLE load_log ADD COLUMN IF NOT EXISTS file_size_mb DOUBLE PRECISION;
ALTER TABLE load_log ADD COLUMN IF NOT EXISTS detected_at TIMESTAMP;
ALTER TABLE load_log ADD COLUMN IF NOT EXISTS ingestion_latency_sec DOUBLE PRECISION;

CREATE TABLE IF NOT EXISTS stg_rejects (
    reject_id      BIGSERIAL PRIMARY KEY,
    source_file    TEXT,
    target_table   TEXT,
    reject_reason  TEXT,
    raw_row        JSONB,
    rejected_at    TIMESTAMP DEFAULT (now() AT TIME ZONE 'UTC')
);

-- ============ DASHBOARD VIEWS ============

-- One row per batch: duration, throughput, reject rate, latency.
-- Feeds: horizontal bar (duration per file), time series (throughput), tables.
CREATE OR REPLACE VIEW v_batch_summary AS
SELECT
    load_id, source_file, target_table, started_at, status,
    file_size_mb, rows_read, rows_loaded, rows_rejected, duration_sec,
    round((rows_loaded   / nullif(duration_sec, 0))::numeric, 0)  AS rows_per_sec,
    round((file_size_mb  / nullif(duration_sec, 0))::numeric, 3)  AS mb_per_sec,
    round((100.0 * rows_rejected / nullif(rows_read, 0))::numeric, 2) AS rejection_rate_pct,
    round(ingestion_latency_sec::numeric, 2)                      AS ingestion_latency_sec
FROM load_log;

-- Single row of headline KPIs. Feeds: KPI cards.
CREATE OR REPLACE VIEW v_ingestion_kpis AS
SELECT
    count(*)                                              AS total_batches,
    count(*) FILTER (WHERE status = 'success')            AS successful_batches,
    count(*) FILTER (WHERE status = 'failed')             AS failed_batches,
    round(100.0 * count(*) FILTER (WHERE status = 'success')
          / nullif(count(*), 0), 1)                       AS success_rate_pct,
    coalesce(sum(rows_loaded), 0)                         AS total_rows_loaded,
    coalesce(sum(rows_rejected), 0)                       AS total_rows_rejected,
    round(100.0 * sum(rows_rejected)
          / nullif(sum(rows_read), 0), 2)                 AS rejection_rate_pct,
    round((sum(rows_loaded) / nullif(sum(duration_sec), 0))::numeric, 0) AS avg_rows_per_sec,
    round(avg(duration_sec)::numeric, 2)                  AS avg_duration_sec,
    round(sum(file_size_mb)::numeric, 2)                  AS total_mb_loaded,
    round(avg(ingestion_latency_sec)::numeric, 2)         AS avg_ingestion_latency_sec,
    max(ended_at) FILTER (WHERE status = 'success')       AS last_success_at,
    round((extract(epoch FROM (
        (now() AT TIME ZONE 'UTC') - max(ended_at) FILTER (WHERE status = 'success')
    )) / 60)::numeric, 1)                                 AS freshness_minutes
FROM load_log;

-- Volume per day. Feeds: rows/files loaded per day.
CREATE OR REPLACE VIEW v_ingestion_daily AS
SELECT
    started_at::date                                      AS day,
    count(*)                                              AS batches,
    count(*) FILTER (WHERE status = 'success')            AS successful,
    count(*) FILTER (WHERE status = 'failed')             AS failed,
    sum(rows_loaded)                                      AS rows_loaded,
    sum(rows_rejected)                                    AS rows_rejected,
    round(sum(file_size_mb)::numeric, 2)                  AS mb_loaded,
    round(100.0 * sum(rows_rejected) / nullif(sum(rows_read), 0), 2) AS rejection_rate_pct,
    round((sum(rows_loaded) / nullif(sum(duration_sec), 0))::numeric, 0) AS rows_per_sec
FROM load_log
GROUP BY 1
ORDER BY 1;

-- Rollup per staging table (source domain). Feeds: bar/donut per source.
CREATE OR REPLACE VIEW v_source_summary AS
SELECT
    target_table,
    count(*)                                              AS batches,
    sum(rows_loaded)                                      AS rows_loaded,
    sum(rows_rejected)                                    AS rows_rejected,
    round(avg(duration_sec)::numeric, 2)                  AS avg_duration_sec,
    round((sum(rows_loaded) / nullif(sum(duration_sec), 0))::numeric, 0) AS rows_per_sec,
    round(100.0 * sum(rows_rejected) / nullif(sum(rows_read), 0), 2)     AS rejection_rate_pct
FROM load_log
WHERE status = 'success'
GROUP BY 1;

-- Rejects by individual reason (a row can have several reasons).
-- Feeds: bar chart of which validation rule fails most.
CREATE OR REPLACE VIEW v_reject_reasons AS
SELECT
    r.target_table,
    reason,
    count(*) AS rejected_rows
FROM stg_rejects r,
     LATERAL regexp_split_to_table(regexp_replace(r.reject_reason, ';\s*$', ''), ';\s*') AS reason
GROUP BY 1, 2
ORDER BY rejected_rows DESC;

-- Failed batches. Feeds: table panel.
CREATE OR REPLACE VIEW v_failed_batches AS
SELECT started_at, source_file, target_table, file_size_mb,
       round(duration_sec::numeric, 2) AS duration_sec, error_message
FROM load_log
WHERE status = 'failed'
ORDER BY started_at DESC;






-- ============ QUERY LAYER METRICS ============
CREATE TABLE IF NOT EXISTS query_log (
    query_id       BIGSERIAL PRIMARY KEY,
    query_name     TEXT NOT NULL,
    variant        TEXT NOT NULL,     -- baseline | indexed | optimized | dashboard ...
    executed_at    TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'UTC'),
    duration_ms    DOUBLE PRECISION,
    rows_returned  INTEGER,
    status         TEXT NOT NULL,     -- success | failed
    error_message  TEXT
);

CREATE OR REPLACE VIEW v_query_kpis AS
SELECT count(*) AS total_queries,
       count(*) FILTER (WHERE status = 'failed') AS failed_queries,
       round(100.0 * count(*) FILTER (WHERE status = 'failed') / nullif(count(*), 0), 2) AS error_rate_pct,
       round((avg(duration_ms) FILTER (WHERE status = 'success'))::numeric, 1) AS avg_ms,
       round((percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms)
              FILTER (WHERE status = 'success'))::numeric, 1) AS p95_ms,
       count(*) FILTER (WHERE executed_at::date = (now() AT TIME ZONE 'UTC')::date) AS queries_today
FROM query_log;

CREATE OR REPLACE VIEW v_query_by_name AS
SELECT query_name, variant, count(*) AS runs,
       round(avg(duration_ms)::numeric, 1) AS avg_ms,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_ms))::numeric, 1) AS median_ms,
       round(min(duration_ms)::numeric, 1) AS min_ms,
       round(max(duration_ms)::numeric, 1) AS max_ms
FROM query_log WHERE status = 'success'
GROUP BY 1, 2;

CREATE OR REPLACE VIEW v_query_daily AS
SELECT executed_at::date AS day, count(*) AS queries,
       count(*) FILTER (WHERE status = 'failed') AS failed,
       round(100.0 * count(*) FILTER (WHERE status = 'failed') / nullif(count(*), 0), 2) AS error_rate_pct,
       round((avg(duration_ms) FILTER (WHERE status = 'success'))::numeric, 1) AS avg_ms
FROM query_log GROUP BY 1 ORDER BY 1;

CREATE OR REPLACE VIEW v_query_speedup AS
SELECT query_name,
  round((percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_ms) FILTER (WHERE variant = 'baseline'))::numeric, 1)  AS baseline_ms,
  round((percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_ms) FILTER (WHERE variant = 'indexed'))::numeric, 1)   AS indexed_ms,
  round((percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_ms) FILTER (WHERE variant = 'optimized'))::numeric, 1) AS optimized_ms,
  round(((percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_ms) FILTER (WHERE variant = 'baseline'))
        / nullif((percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_ms) FILTER (WHERE variant = 'optimized')), 0))::numeric, 1) AS speedup_x
FROM query_log
WHERE status = 'success' AND variant IN ('baseline', 'indexed', 'optimized')
GROUP BY 1;