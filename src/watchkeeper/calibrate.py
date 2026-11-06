"""Turn the raw alert score into a probability that the diagnosis is right.

The raw score is not a probability (rule-based alerts carry fixed numbers, the forest's share is not calibrated). A small logistic
regression maps (raw score, which part of the pipeline produced the alert) to P(the named fault type matches a labelled event),
fitted on leave-one-asset-out predictions, so it learns from alerts the model made on pumps it had not seen.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

RULES = ["rule_gap", "rule_stuck", "rule_arbiter", "cavitation"]          # anything else counts as "model"
DEFAULT_PATH = Path(__file__).resolve().parents[2] / "models" / "calibrator.json"


def _design(pred: pd.DataFrame) -> np.ndarray:
    raw = pred["confidence"].astype(float).to_numpy()
    rule = pred["rule"].fillna("model").to_numpy() if "rule" in pred else np.array(["model"] * len(pred))
    return np.column_stack([raw] + [(rule == r).astype(float) for r in RULES])


class Calibrator:
    def __init__(self, C: float = 2.0):
        self.C = C
        self.coef: list[float] | None = None
        self.intercept: float | None = None
        self.meta: dict = {}

    def fit(self, pred: pd.DataFrame, target: str = "type_ok", **meta) -> "Calibrator":
        lr = LogisticRegression(C=self.C, max_iter=1000).fit(_design(pred), pred[target].astype(int))
        self.coef, self.intercept = lr.coef_[0].tolist(), float(lr.intercept_[0])
        self.meta = {"target": target, "n_alerts": int(len(pred)), "base_rate": float(pred[target].mean()), "C": self.C, **meta}
        return self

    def predict(self, pred: pd.DataFrame) -> np.ndarray:
        z = _design(pred) @ np.asarray(self.coef) + self.intercept
        return 1.0 / (1.0 + np.exp(-z))

    def to_dict(self) -> dict:
        return {"features": ["raw_confidence"] + RULES, "coef": self.coef, "intercept": self.intercept, "meta": self.meta}

    def save(self, path=DEFAULT_PATH) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        return path

    @classmethod
    def load(cls, path=DEFAULT_PATH) -> "Calibrator | None":
        path = Path(path)
        if not path.exists():
            return None
        d = json.loads(path.read_text(encoding="utf-8"))
        c = cls()
        c.coef, c.intercept, c.meta = d["coef"], d["intercept"], d.get("meta", {})
        return c


def apply_calibration(pred: pd.DataFrame, cal: Calibrator | None) -> pd.DataFrame:
    """Replace `confidence` with the calibrated probability (the raw score is kept in `raw_confidence`) and rescale the alternatives
    so that together with the main diagnosis they add up to at most one."""
    if cal is None or pred.empty:
        return pred
    out = pred.copy()
    out["raw_confidence"] = out["confidence"]
    out["confidence"] = np.round(np.clip(cal.predict(out), 0.02, 0.98), 3)
    if "alternatives" in out:
        def rescale(alts_json, conf):
            alts = json.loads(alts_json) if isinstance(alts_json, str) and alts_json else []
            total = sum(a["p"] for a in alts)
            return json.dumps([{"fault_type": a["fault_type"], "p": round(a["p"] / total * (1 - conf), 3)} for a in alts]) if total > 0 else "[]"
        out["alternatives"] = [rescale(a, c) for a, c in zip(out["alternatives"], out["confidence"])]
    return out


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def reliability(p: np.ndarray, y: np.ndarray, edges=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0001)) -> tuple[pd.DataFrame, float]:
    """Table of (bin, n, mean predicted, observed rate) and the expected calibration error."""
    rows, ece = [], 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi)
        if m.sum():
            rows.append({"bin": f"{lo:.1f}-{min(hi, 1.0):.1f}", "n": int(m.sum()), "mean_predicted": float(p[m].mean()), "observed": float(y[m].mean())})
            ece += m.sum() / len(p) * abs(p[m].mean() - y[m].mean())
    return pd.DataFrame(rows), float(ece)


def nested_calibration(pred: pd.DataFrame, target: str = "type_ok", C: float = 2.0) -> np.ndarray:
    """Calibrated probabilities where every pump's alerts are calibrated by a calibrator that has not seen that pump."""
    out = np.zeros(len(pred))
    for a in pred["asset_id"].unique():
        te = (pred["asset_id"] == a).to_numpy()
        out[te] = Calibrator(C).fit(pred[~te], target).predict(pred[te])
    return out
