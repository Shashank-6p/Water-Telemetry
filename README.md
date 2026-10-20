# Industrial Water Treatment Telemetry & Anomaly Pipeline (DIKW)

End-to-end data pipeline that simulates sensor telemetry from 50 water treatment plants, models it into a
Kimball star schema with automated data-quality tests, and predicts **pump failures 2 hours in advance**
to drive maintenance dispatch alerts.

> Data is **synthetic**. Failures are simulated with a 2-hour pressure-drift precursor, so model scores are
> optimistic compared with real-world sensor data.

## Architecture (DIKW)

```
[Simulator] -> [Raw warehouse tables] -> [dbt star schema + tests] -> [RandomForest] -> [Alerts dashboard]
   DATA             INFORMATION               KNOWLEDGE                  WISDOM             WISDOM
 simulate.py          ingest.py              dbt_project/                train.py        app/streamlit_app.py
```

| Layer | What it does | Where |
|---|---|---|
| Data | 5 sensors x 50 plants, 15-min readings, injected pump failures and pH spikes | `src/simulate.py` |
| Information | Daily batch loads into raw (bronze) tables | `src/ingest.py`, `dags/` |
| Knowledge | `stg_readings` -> `dim_facility`, `dim_sensor`, `fact_sensor_readings` + 9 data tests | `dbt_project/` |
| Wisdom | RandomForest early-warning model, P1/P2 dispatch recommendations, dashboard | `src/train.py`, `app/` |

## Project structure

```
.
├── src/                 # simulate, ingest, train, run_pipeline, config
├── dbt_project/         # models (staging + marts), schema tests, singular pH test
├── dags/                # Airflow DAG: load -> dbt build -> train
├── app/                 # Streamlit dashboard
├── tests/               # pytest unit tests
├── notebooks/           # single-file Colab version of the whole project
├── .github/workflows/   # CI: pytest + full pipeline run
├── Makefile
└── requirements.txt
```

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m src.run_pipeline      # simulate -> load -> dbt build (models + tests) -> train
streamlit run app/streamlit_app.py
pytest -q
```

Run a single stage: `python -m src.run_pipeline --stage load|dbt|train`.

## Results (test set = last day, chronological split)

| Metric | Value |
|---|---|
| ROC-AUC | ~0.98 |
| Precision (alert at risk >= 0.5) | ~0.93 |
| Recall | ~0.85 |

## Data quality tests (dbt)

- `sensor_id`: not null, unique in `dim_sensor`, relationship to `dim_sensor`
- `facility_id`: unique in `dim_facility`, relationship from the fact table
- `value`: not null
- Singular test: pH must be between 0 and 14

## Design notes

- **Time-based split** (train on days 1-2, test on day 3) to avoid leaking future data.
- **Label** = a pump failure starts within the next 2 hours; rows during the failure are excluded.
- **Idempotent staging**: `stg_readings` keeps only the latest load per sensor/timestamp.
- **DuckDB** is the local warehouse. For GCP BigQuery: install `dbt-bigquery`, add a target in
  `dbt_project/profiles.yml`, and replace the DuckDB load in `src/ingest.py` with a BigQuery load job.
- **Airflow**: mount this repo at `/opt/airflow/project` in your Airflow Docker setup and enable `water_telemetry_pipeline`.

## Possible extensions

Noisier / harder failure patterns, threshold tuning, Docker Compose for Airflow, BigQuery deployment, model monitoring.
