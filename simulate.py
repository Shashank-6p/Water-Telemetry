"""DATA layer: simulate telemetry from water treatment plants with injected anomalies.

- pump_failure: pressure drifts down for 2 hours, then collapses (predictable)
- ph_spike:     sudden pH jump (not predictable, caught by a rule)
"""
import numpy as np
import pandas as pd

from .config import FAILURE_STEPS, FREQ, HORIZON_STEPS, N_PLANTS, SEED, START, STEPS, UNITS


def generate(n_plants: int = N_PLANTS, steps: int = STEPS, seed: int = SEED):
    rng = np.random.default_rng(seed)
    ts = pd.date_range(START, periods=steps, freq=FREQ)
    t_idx = np.arange(steps)

    facilities = pd.DataFrame({
        "facility_id": [f"WTP-{i:03d}" for i in range(1, n_plants + 1)],
        "facility_name": [f"Plant {i}" for i in range(1, n_plants + 1)],
        "region": rng.choice(["North", "South", "East", "West"], n_plants),
        "capacity_m3_h": rng.choice([300, 500, 800, 1200], n_plants),
    })

    rows, events = [], []
    for fid, cap in zip(facilities.facility_id, facilities.capacity_m3_h):
        d = {
            "ph": rng.normal(7.2, 0.08, steps),
            "turbidity": np.abs(rng.normal(0.8, 0.15, steps)),
            "flow": cap * 0.6 * (1 + 0.1 * np.sin(2 * np.pi * t_idx / 96)) + rng.normal(0, cap * 0.01, steps),
            "pressure": rng.normal(4.0, 0.08, steps),
            "chem_dose": rng.normal(2.0, 0.1, steps),
        }
        for _ in range(rng.integers(1, 3)):  # 1-2 pump failures per plant
            t = int(rng.integers(20, steps - HORIZON_STEPS))
            for i in range(t - HORIZON_STEPS, t):
                frac = (i - (t - HORIZON_STEPS) + 1) / HORIZON_STEPS
                d["pressure"][i] -= 1.0 * frac
                d["flow"][i] *= 1 - 0.08 * frac
            d["pressure"][t:t + FAILURE_STEPS] -= 2.5
            d["flow"][t:t + FAILURE_STEPS] *= 0.4
            events.append((fid, ts[t], "pump_failure"))
        for t in rng.choice(steps, 3, replace=False):  # 3 pH spikes per plant
            d["ph"][t] += rng.choice([-2.0, 2.5])
            events.append((fid, ts[t], "ph_spike"))
        for sensor, values in d.items():
            rows.append(pd.DataFrame({
                "facility_id": fid, "sensor_id": f"{fid}-{sensor}", "sensor_type": sensor,
                "unit": UNITS[sensor], "reading_ts": ts, "value": values.round(3),
            }))

    raw = pd.concat(rows, ignore_index=True)
    events = pd.DataFrame(events, columns=["facility_id", "event_ts", "event_type"])
    return raw, facilities, events
