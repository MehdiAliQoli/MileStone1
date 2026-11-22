FROM apache/airflow:2.9.3
RUN pip install --no-cache-dir --default-timeout=300 --retries 10 \
    duckdb==2.0.1 watchdog python-dotenv openpyxl