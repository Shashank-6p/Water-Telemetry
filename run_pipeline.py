"""Run the full pipeline or a single stage:  python -m src.run_pipeline [--stage load|dbt|train|all]"""
import argparse
import os
import subprocess
import sys

from .config import DB_PATH, DBT_DIR
from . import ingest, simulate, train


def run_load():
    raw, facilities, events = simulate.generate()
    print(f"simulated {raw.shape[0]} readings, {len(events)} events")
    ingest.load_raw(raw, facilities, events)


def run_dbt():
    env = {**os.environ, "DUCKDB_PATH": str(DB_PATH)}
    res = subprocess.run(["dbt", "build", "--profiles-dir", "."], cwd=DBT_DIR, env=env)
    if res.returncode != 0:
        sys.exit("dbt build failed (a model or data-quality test failed)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["load", "dbt", "train", "all"], default="all")
    stage = parser.parse_args().stage
    if stage in ("load", "all"):
        run_load()
    if stage in ("dbt", "all"):
        run_dbt()
    if stage in ("train", "all"):
        train.main()


if __name__ == "__main__":
    main()
