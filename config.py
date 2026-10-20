from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ARTIFACTS_DIR = ROOT / "artifacts"
DB_PATH = DATA_DIR / "warehouse.duckdb"
DBT_DIR = ROOT / "dbt_project"

N_PLANTS = 50
STEPS = 288            # 3 days of 15-minute readings
FREQ = "15min"
START = "2026-01-01"
SEED = 42
HORIZON_STEPS = 8      # 8 x 15 min = 2 hours of early warning
FAILURE_STEPS = 4      # rows during the failure itself (excluded from ML)

UNITS = {"ph": "pH", "turbidity": "NTU", "flow": "m3/h", "pressure": "bar", "chem_dose": "mg/L"}
