import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
SEED_DIR = DATA_DIR / "seed"
LANDING_DIR = DATA_DIR / "landing"
PROCESSED_DIR = DATA_DIR / "processed"
FAILED_DIR = DATA_DIR / "failed"
WAREHOUSE_DIR = BASE_DIR / "warehouse"
DUCKDB_PATH = WAREHOUSE_DIR / "sdi_mart.duckdb"

PG = dict(
    host=os.getenv("PG_HOST", "localhost"),
    port=int(os.getenv("PG_PORT", "5433")),
    dbname=os.getenv("POSTGRES_DB", "pharma_staging"),
    
    user=os.getenv("POSTGRES_USER", "pharma"),
    password=os.getenv("POSTGRES_PASSWORD", "pharma123"),
)

# file-name prefix -> staging table (Phase 1 uses only these 3 sources)
FILE_TABLE_MAP = [
    ("01_", "stg_master"),
    ("04_", "stg_warehouse"),
    ("05_", "stg_sales"),
    ("06_", "stg_hospital_demand"),
]