"""INFORMATION layer: batch-load raw data into the warehouse (DuckDB locally, BigQuery in production)."""
import duckdb

from .config import DATA_DIR, DB_PATH


def load_raw(raw, facilities, events, db_path=DB_PATH):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.register("raw_df", raw)
    con.execute("create or replace table raw_sensor_readings as select *, now() as _loaded_at from raw_df where 1=0")

    for day, batch in raw.groupby(raw.reading_ts.dt.date):  # one batch per day, like a scheduled run
        con.register("batch_df", batch)
        con.execute("insert into raw_sensor_readings select *, now() from batch_df")
        print(f"loaded batch {day}: {len(batch)} rows")

    con.register("fac_df", facilities)
    con.register("evt_df", events)
    con.execute("create or replace table raw_facilities as select * from fac_df")
    con.execute("create or replace table raw_events as select * from evt_df")
    con.close()  # DuckDB allows a single writer; release it so dbt can connect
