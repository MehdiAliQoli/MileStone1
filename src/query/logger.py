import psycopg2
from src.config import PG
from src.ingestion.metrics import utcnow


def log_query(query_name, variant, duration_ms, rows_returned, status, error=None):
    """Logging must never break a query run, so failures here only warn."""
    try:
        conn = psycopg2.connect(**PG)
        try:
            with conn, conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO query_log (query_name, variant, executed_at, duration_ms, "
                    "rows_returned, status, error_message) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (query_name, variant, utcnow(), duration_ms, rows_returned, status, error))
        finally:
            conn.close()
    except Exception as e:
        print(f"[warn] could not write query_log: {e}")