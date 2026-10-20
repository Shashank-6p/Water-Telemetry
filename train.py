"""WISDOM layer: predict pump failures 2 hours ahead and generate dispatch recommendations."""
import json

import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score

from .config import ARTIFACTS_DIR, DB_PATH, FAILURE_STEPS, FREQ, HORIZON_STEPS

FEATURES = ["ph", "turbidity", "pressure", "chem_dose", "flow_ratio",
            "p_diff1", "p_diff8", "p_mean4", "p_std4", "f_mean4"]


def load_from_warehouse(db_path=DB_PATH):
    con = duckdb.connect(str(db_path), read_only=True)
    fact = con.execute("""
        select f.facility_id, f.reading_ts, s.sensor_type, f.value
        from fact_sensor_readings f join dim_sensor s using (sensor_id)
    """).df()
    dim_fac = con.execute("select * from dim_facility").df()
    events = con.execute("select * from raw_events").df()
    con.close()
    return fact, dim_fac, events


def pivot(fact):
    return (fact.pivot_table(index=["facility_id", "reading_ts"], columns="sensor_type", values="value")
                .reset_index().sort_values(["facility_id", "reading_ts"]).reset_index(drop=True))


def add_labels(wide, events):
    """label=1 if a pump failure starts within the next 2 hours; failure rows themselves are flagged."""
    step = pd.Timedelta(FREQ)
    wide = wide.copy()
    wide["label"], wide["in_failure"] = 0, False
    failures = events[events.event_type == "pump_failure"]
    for fid, t in failures[["facility_id", "event_ts"]].itertuples(index=False):
        m = wide.facility_id == fid
        wide.loc[m & (wide.reading_ts >= t - HORIZON_STEPS * step) & (wide.reading_ts < t), "label"] = 1
        wide.loc[m & (wide.reading_ts >= t) & (wide.reading_ts < t + FAILURE_STEPS * step), "in_failure"] = True
    return wide


def add_features(wide):
    wide = wide.copy()
    wide["flow_ratio"] = wide.flow / wide.groupby("facility_id").flow.transform("median")
    g = wide.groupby("facility_id")
    wide["p_diff1"] = g.pressure.diff()
    wide["p_diff8"] = g.pressure.diff(HORIZON_STEPS)
    wide["p_mean4"] = g.pressure.transform(lambda s: s.rolling(4, min_periods=1).mean())
    wide["p_std4"] = g.pressure.transform(lambda s: s.rolling(4, min_periods=2).std())
    wide["f_mean4"] = g.flow_ratio.transform(lambda s: s.rolling(4, min_periods=1).mean())
    wide[FEATURES] = wide[FEATURES].fillna(0)
    return wide


def recommend(risk):
    if risk >= 0.8:
        return "P1: dispatch engineer now - inspect pump & pressure line"
    if risk >= 0.5:
        return "P2: schedule inspection within 2 hours"
    return "OK"


def main():
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    fact, dim_fac, events = load_from_warehouse()
    wide = add_features(add_labels(pivot(fact), events))

    uniq = np.sort(wide.reading_ts.unique())
    cutoff = uniq[int(len(uniq) * 2 / 3)]  # chronological split: no leakage from the future
    train = wide[(wide.reading_ts < cutoff) & ~wide.in_failure]
    test = wide[(wide.reading_ts >= cutoff) & ~wide.in_failure].copy()

    model = RandomForestClassifier(n_estimators=200, max_depth=8, class_weight="balanced",
                                   random_state=42, n_jobs=-1)
    model.fit(train[FEATURES], train.label)
    test["risk"] = model.predict_proba(test[FEATURES])[:, 1]

    report = classification_report(test.label, test.risk >= 0.5, output_dict=True)
    metrics = {"roc_auc": round(roc_auc_score(test.label, test.risk), 3),
               "precision": round(report["1"]["precision"], 3),
               "recall": round(report["1"]["recall"], 3)}
    print("Metrics:", metrics)

    test = test.merge(dim_fac[["facility_id", "region"]], on="facility_id")
    alerts = (test[test.risk >= 0.5].groupby(["facility_id", "region"])
              .agg(first_alert=("reading_ts", "min"), alert_rows=("risk", "size"), max_risk=("risk", "max"))
              .reset_index().sort_values("max_risk", ascending=False))
    alerts["recommendation"] = alerts.max_risk.map(recommend)
    health = (test.sort_values("reading_ts").groupby("facility_id").tail(1)
              [["facility_id", "region", "reading_ts", "pressure", "ph", "risk"]]
              .sort_values("risk", ascending=False))

    alerts.to_csv(ARTIFACTS_DIR / "alerts.csv", index=False)
    health.to_csv(ARTIFACTS_DIR / "health.csv", index=False)
    test[["facility_id", "reading_ts", "pressure", "ph", "risk", "label"]].to_csv(
        ARTIFACTS_DIR / "test_scores.csv", index=False)
    (ARTIFACTS_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
    joblib.dump(model, ARTIFACTS_DIR / "rf_model.joblib")
    print(f"Plants alerting: {len(alerts)} | artifacts saved to {ARTIFACTS_DIR}")
    return metrics


if __name__ == "__main__":
    main()
