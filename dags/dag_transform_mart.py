from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator


def run_transform():
    from src.transform.run_transform import run
    run()


def validate_mart():
    from src.transform.validate import main
    main()


with DAG("dag_transform_mart", start_date=datetime(2026, 1, 1),
         schedule=None, catchup=False, tags=["pharma"]) as dag:
    t_run = PythonOperator(task_id="dims_then_facts", python_callable=run_transform)
    t_val = PythonOperator(task_id="validate_mart", python_callable=validate_mart)
    t_next = TriggerDagRunOperator(task_id="trigger_refresh", trigger_dag_id="dag_refresh_summaries")
    t_run >> t_val >> t_next