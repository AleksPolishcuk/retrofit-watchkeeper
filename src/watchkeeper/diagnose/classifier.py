"""Learned diagnosis: a random forest over causal deviation features, trained on labelled event minutes.

Training rows are the minutes that would count as deviating (|z| above `k_low`, a data gap or a frozen channel).
Each labelled event contributes equal total weight, whatever its length. Deviating minutes that belong to no event
(start-ups, weather, load changes) are labelled NONE, so that the model can also say "probably nothing".
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from ..detect.alerting import b1_flag

NONE = "NONE"
SOFT_END = {"CAVITATION", "AIR_ENTRAINMENT"}
SENSOR_TYPES = {"SENSOR_DRIFT", "SENSOR_STUCK", "SENSOR_CALIBRATION_SHIFT", "SENSOR_NOISE_SPIKES", "COMMUNICATION_LOSS"}
ACTIONS = {
    "BEARING_WEAR": "Inspect the pump bearing, check lubrication and plan a bearing change in the next window.",
    "SUCTION_STRAINER_CLOGGING": "Inspect and clean the suction strainer at the next opportunity.",
    "CAVITATION": "Check suction level and strainer; avoid operating at the flow that causes it if the process allows.",
    "DISCHARGE_RESTRICTION": "Check discharge valve position and heat-exchanger fouling.",
    "MISALIGNMENT": "Check coupling alignment, especially after recent maintenance.",
    "IMBALANCE": "Inspect the impeller for fouling or damage and balance if needed.",
    "IMPELLER_WEAR": "Run a performance test and inspect the impeller and wear rings.",
    "AIR_ENTRAINMENT": "Check suction level and sea-chest aeration; inspect for air ingress.",
    "SENSOR_DRIFT": "Check the transmitter against a reference gauge before any repair.",
    "SENSOR_STUCK": "Check the sensor and its wiring; the value is not changing.",
    "SENSOR_CALIBRATION_SHIFT": "Verify the transmitter calibration against a reference gauge.",
    "SENSOR_NOISE_SPIKES": "Check the sensor wiring, shielding and power supply.",
    "COMMUNICATION_LOSS": "Check the gateway and network link. No fault can be assessed during the gap.",
    "UNKNOWN": "Something is off but the cause is unclear. Schedule a performance check.",
}


def event_class_of(fault_type: str) -> str:
    return "SENSOR" if fault_type in SENSOR_TYPES else "MACHINE"


def _ts(x):
    return pd.to_datetime(x, utc=True, format="ISO8601")


class DiagnosisModel:
    def __init__(self, k_low: float = 4.0, none_weight: float = 0.5, trees: int = 300, seed: int = 0):
        self.k_low, self.none_weight, self.trees, self.seed = k_low, none_weight, trees, seed
        self.model: RandomForestClassifier | None = None
        self.classes_: list[str] = []

    def training_set(self, zf: pd.DataFrame, X: pd.DataFrame, events: pd.DataFrame, ids) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
        xs, ys, ws, none_parts = [], [], [], []
        n_events_used = 0
        for a in ids:
            g = zf[zf.asset_id == a]
            if g.empty:
                continue
            t = g["window_start_utc"]
            t_end = t.max() + pd.Timedelta(minutes=1)
            flag = b1_flag(g, self.k_low)
            covered = np.zeros(len(g), dtype=bool)
            Xa = X.loc[g.index]
            for e in events[events.asset_id == a].itertuples():
                soft = e.fault_type in SOFT_END or e.event_class == "SENSOR"
                end = t_end if pd.isna(e.end_utc) else _ts(e.end_utc) + (pd.Timedelta(minutes=30) if soft else pd.Timedelta(0))
                onset = _ts(e.onset_utc)
                covered |= ((t >= onset) & (t <= end)).to_numpy()
                if pd.isna(e.detectable_utc) or str(e.observable).lower() not in ("true", "1"):
                    continue
                start = max(_ts(e.detectable_utc), onset)
                m = ((t >= start) & (t <= end)).to_numpy() & flag
                if m.sum():
                    xs.append(Xa[m])
                    ys += [e.fault_type] * int(m.sum())
                    ws.append(np.full(int(m.sum()), 1.0 / m.sum()))
                    n_events_used += 1
            m = flag & ~covered
            if m.sum():
                none_parts.append(Xa[m])
        if none_parts:
            Xn = pd.concat(none_parts)
            xs.append(Xn)
            ys += [NONE] * len(Xn)
            ws.append(np.full(len(Xn), self.none_weight * max(n_events_used, 1) / len(Xn)))
        return pd.concat(xs), np.array(ys), np.concatenate(ws)

    def fit(self, zf, X, events, ids) -> "DiagnosisModel":
        Xt, y, w = self.training_set(zf, X, events, ids)
        self.model = RandomForestClassifier(n_estimators=self.trees, min_samples_leaf=3, random_state=self.seed, n_jobs=-1)
        self.model.fit(Xt.to_numpy(), y, sample_weight=w * len(w) / w.sum())
        self.classes_ = [str(c) for c in self.model.classes_]
        return self

    def proba(self, Xa: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(Xa.to_numpy())
