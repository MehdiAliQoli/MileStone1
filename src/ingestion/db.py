import psycopg2
from src.config import PG, BASE_DIR


def get_conn():
    return psycopg2.connect(**PG)


def init_schema():
    sql_text = (BASE_DIR / "sql" / "staging" / "create_staging.sql").read_text()
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql_text)
    finally:
        conn.close()


if __name__ == "__main__":
    init_schema()
    print("staging schema ready (load_log, stg_rejects)")