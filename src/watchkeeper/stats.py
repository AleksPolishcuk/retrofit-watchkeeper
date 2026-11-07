"""Intervals and null detectors for the composite score. Events cluster by pump, so intervals resample pumps, not events."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .evalkit import DevData, score_ids


def per_asset(pred: pd.DataFrame, data: DevData) -> dict:
    """Sufficient statistics per pump, enough to rebuild the composite for any resampled set of pumps."""
    out = {}
    for a in data.ids:
        r = score_ids(pred[pred.asset_id == a] if len(pred) else pred, data, [a])
        pe = pd.DataFrame(r["per_event"])
        out[a] = dict(n=len(pe), tp=r["true_positive_events"], ep=r["false_alert_episodes"] + r["excess_repeat_episodes"], days=r["asset_days"],
                      tl=float(pe.timeliness.sum()) if len(pe) else 0.0, ty=float(pe.type_correct.sum()) if len(pe) else 0.0,
                      cl=float(pe.class_correct.sum()) if len(pe) else 0.0)
    return out


def composite(rows: list) -> float:
    n = sum(r["n"] for r in rows)
    if n == 0:
        return float("nan")
    tp, ep, days = sum(r["tp"] for r in rows), sum(r["ep"] for r in rows), sum(r["days"] for r in rows)
    rec = tp / n
    pre = tp / (tp + ep) if tp + ep else 0.0
    f1 = 2 * pre * rec / (pre + rec) if pre + rec else 0.0
    return 100 * (0.35 * f1 + 0.20 * sum(r["tl"] for r in rows) / n + 0.25 * sum(r["ty"] for r in rows) / n + 0.10 * sum(r["cl"] for r in rows) / n
                  + 0.10 * max(0.0, 1 - ep / days / 2))


def bootstrap(stats: dict, reps: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    ids, rng = list(stats), np.random.default_rng(seed)
    v = [composite([stats[i] for i in rng.choice(ids, size=len(ids), replace=True)]) for _ in range(reps)]
    lo, mid, hi = np.nanpercentile(v, [2.5, 50, 97.5])
    return float(lo), float(mid), float(hi)


def random_alerts(pred: pd.DataFrame, data: DevData, draws: int = 20, seed: int = 0) -> float:
    """Composite of a detector that raises as many alerts per pump as `pred`, at random times, with types drawn from the same mix."""
    rng = np.random.default_rng(seed)
    assets = data.assets.set_index("asset_id")
    mix = pred[["event_class", "fault_type"]].drop_duplicates()
    weights = pred.groupby(["event_class", "fault_type"]).size().reindex(pd.MultiIndex.from_frame(mix)).to_numpy().astype(float)
    weights /= weights.sum()
    scores = []
    for _ in range(draws):
        rows = []
        for a in data.ids:
            n = int((pred.asset_id == a).sum())
            t0, t1 = pd.Timestamp(assets.loc[a, "window_start_utc"]), pd.Timestamp(assets.loc[a, "window_end_utc"])
            for _i in range(n):
                k = rng.choice(len(mix), p=weights)
                rows.append({"asset_id": a, "alert_time_utc": (t0 + (t1 - t0) * float(rng.random())).strftime("%Y-%m-%dT%H:%M:%SZ"),
                             "event_class": mix.iloc[k].event_class, "fault_type": mix.iloc[k].fault_type, "confidence": 0.5, "evidence": "", "recommended_action": ""})
        scores.append(score_ids(pd.DataFrame(rows, columns=["asset_id", "alert_time_utc", "event_class", "fault_type", "confidence", "evidence", "recommended_action"]),
                                data, data.ids)["composite_score"])
    return float(np.mean(scores))


def poisson_upper(k: int, exposure_days: float, level: float = 0.975) -> float:
    """Upper confidence bound on a rate (events per day) after seeing k events in `exposure_days`."""
    from scipy.stats import chi2
    return float(chi2.ppf(level, 2 * (k + 1)) / 2 / exposure_days)
