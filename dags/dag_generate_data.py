from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator


def generate_sales():
    from src.generator.generate_sales import generate
    generate(rows=50_000)


def generate_demand():
    from src.generator.generate_demand import generate
    generate()


with DAG("dag_generate_data", start_date=datetime(2026, 1, 1),
         schedule=None,            # manual; use "*/30 * * * *" to refresh automatically
         catchup=False, tags=["pharma"]) as dag:
    t_sales = PythonOperator(task_id="generate_sales", python_callable=generate_sales)
    t_demand = PythonOperator(task_id="generate_demand", python_callable=generate_demand)
    t_next = TriggerDagRunOperator(task_id="trigger_ingest", trigger_dag_id="dag_ingest_and_stage")
    t_sales >> t_demand >> t_next      # sequential: both share one state file