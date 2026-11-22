from datetime import datetime, timezone
from src.ingestion.db import get_conn


def utcnow():
    """Naive UTC timestamp, so Windows host and Docker agree."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def already_loaded(source_file):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM load_log WHERE source_file = %s AND status = 'success' LIMIT 1",
                (source_file,),
            )
            return cur.fetchone() is not None
    finally:
        conn.close()


def log_batch(source_file, target_table, started_at, status,
              rows_read=0, rows_loaded=0, rows_rejected=0, error=None,
              file_size_mb=None, detected_at=None):
    ended = utcnow()
    duration = (ended - started_at).total_seconds()
    latency = (started_at - detected_at).total_seconds() if detected_at else None
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO load_log
                   (source_file, target_table, started_at, ended_at, duration_sec,
                    rows_read, rows_loaded, rows_rejected, status, error_message,
                    file_size_mb, detected_at, ingestion_latency_sec)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (source_file, target_table, started_at, ended, duration,
                 rows_read, rows_loaded, rows_rejected, status, error,
                 file_size_mb, detected_at, latency),
            )
    finally:
        conn.close()
    return duration