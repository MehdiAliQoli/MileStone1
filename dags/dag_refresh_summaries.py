from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator


def refresh():
    from src.query.optimize import refresh_summaries
    from src.transform.duck import connect
    con = connect()
    try:
        refresh_summaries(con)
    finally:
        con.close()


def stats_snapshot():
    from src.storage_stats import snapshot
    snapshot()


with DAG("dag_refresh_summaries", start_date=datetime(2026, 1, 1),
         schedule=None, catchup=False, tags=["pharma"]) as dag:
    t_refresh = PythonOperator(task_id="refresh_summary_tables", python_callable=refresh)
    t_stats = PythonOperator(task_id="storage_stats_snapshot", python_callable=stats_snapshot)
    t_refresh >> t_stats