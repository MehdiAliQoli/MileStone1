from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator


def ingest_landing_files():
    from src.config import LANDING_DIR
    from src.ingestion.loader import load_file
    files = sorted(LANDING_DIR.glob("0*_*.csv"))
    print(f"{len(files)} file(s) in landing")
    for f in files:
        load_file(f, move=True)       # validate -> stage -> load_log -> move to processed/failed


with DAG("dag_ingest_and_stage", start_date=datetime(2026, 1, 1),
         schedule=None, catchup=False, tags=["pharma"]) as dag:
    t_ingest = PythonOperator(task_id="ingest_landing_files", python_callable=ingest_landing_files)
    t_next = TriggerDagRunOperator(task_id="trigger_transform", trigger_dag_id="dag_transform_mart")
    t_ingest >> t_next