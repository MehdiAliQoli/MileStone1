CREATE TABLE IF NOT EXISTS etl_watermark (
    source_table  VARCHAR PRIMARY KEY,
    last_row_id   BIGINT
);

CREATE SEQUENCE IF NOT EXISTS transform_log_seq;
CREATE TABLE IF NOT EXISTS transform_log (
    run_id         BIGINT DEFAULT nextval('transform_log_seq'),
    step           VARCHAR,
    started_at     TIMESTAMP,
    ended_at       TIMESTAMP,
    duration_sec   DOUBLE,
    rows_affected  BIGINT,
    status         VARCHAR,
    error_message  VARCHAR
);