"""Ingestion API: upload a source file over HTTP, it goes through the same
validate -> stage -> load_log path as the file watcher.

Run from the project root:
    python -m uvicorn src.api.main:app --port 8000
Then open http://localhost:8000/docs
"""
import shutil
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from src.config import DATA_DIR
from src.ingestion.db import get_conn
from src.ingestion.loader import already_loaded, load_file, resolve_table

INBOX = DATA_DIR / "api_inbox"      # not `landing`, so the watcher doesn't also pick it up
app = FastAPI(title="Pharma DWH Ingestion API")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest")
def ingest(file: UploadFile = File(...)):
    name = Path(file.filename).name
    if resolve_table(name) is None:
        raise HTTPException(400, f"'{name}' must start with 01_, 05_ or 06_")
    if already_loaded(name):
        raise HTTPException(409, f"'{name}' was already loaded")

    INBOX.mkdir(parents=True, exist_ok=True)
    dest = INBOX / name
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    load_file(dest, move=True)       # same validate -> stage -> log path as the watcher

    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT status, target_table, rows_read, rows_loaded, rows_rejected, "
                "duration_sec, error_message FROM load_log "
                "WHERE source_file = %s ORDER BY load_id DESC LIMIT 1", (name,))
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(500, "load finished but no load_log row was found")

    keys = ["status", "table", "rows_read", "rows_loaded", "rows_rejected",
            "duration_sec", "error"]
    result = {"file": name, **dict(zip(keys, row))}
    if result["status"] != "success":
        raise HTTPException(422, result)
    return result