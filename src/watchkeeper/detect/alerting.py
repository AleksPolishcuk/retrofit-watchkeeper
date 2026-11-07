"""Alert timing shared by the methods. Same trigger as organizer B1 (sustained deviation), with a pluggable diagnosis."""
from __future__ import annotations

import json
from typing import Callable

import numpy as np
import pandas as pd

REFRACTORY = pd.Timedelta(hours=12)
REPEAT_EVERY_MIN = 720


def b1_flag(g: pd.DataFrame, k: float) -> np.ndarray:
    """Minutes that count as deviating: steady and |z| or std-z above k, or a data gap, or a frozen channel."""
    zc = [c for c in g.columns if c.startswith("z_")]
    zs = [c for c in g.columns if c.startswith("zs_")]
    Z = g[zc].abs().fillna(0.0).to_numpy()
    S = g[zs].fillna(0.0).to_numpy() if zs else np.zeros((len(g), 1))
    zmax = np.maximum(Z.max(axis=1), S.max(axis=1) / 2.0)
    fl = [c for c in g.columns if c.startswith("flat_")]
    flat = (g[fl].fillna(False).astype(bool).any(axis=1).to_numpy() & g["steady"].to_numpy()) if fl else np.zeros(len(g), dtype=bool)
    return (g["steady"].to_numpy() & (zmax > k)) | g["gap"].to_numpy() | flat


def alerts_from_flag(g: pd.DataFrame, flag: np.ndarray, persist: int, diag: Callable[[int], dict | None], source: str) -> list[dict]:
    """Alert when the flag has held for `persist` minutes, then once per 12 h while it persists.

    `diag(j)` returns the diagnosis for minute index j, or None to suppress the alert.
    """
    rows, run, last = [], 0, {}
    for j in range(len(g)):
        run = run + 1 if flag[j] else 0
        if run == persist or (run > persist and (run - persist) % REPEAT_EVERY_MIN == 0):
            d = diag(j)
            if d is None:
                continue
            t = g["window_start_utc"].iloc[j] + pd.Timedelta(minutes=1)
            if d["fault_type"] not in last or t - last[d["fault_type"]] > REFRACTORY:
                rows.append({"asset_id": g["asset_id"].iloc[j], "alert_time_utc": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                             "event_class": d["event_class"], "fault_type": d["fault_type"], "confidence": float(d["confidence"]),
                             "evidence": f"{source}: {d['evidence']}", "recommended_action": d["action"],
                             "rule": d.get("rule", "model"), "alternatives": json.dumps(d.get("alternatives", []))})
                last[d["fault_type"]] = t
    return rows


def split_flags(g: pd.DataFrame, k: float) -> dict[str, np.ndarray]:
    """The three reasons a minute can count as deviating, kept apart so that each has its own persistence counter.

    With one shared flag, a gateway outage that starts while an earlier deviation is still running never raises its own alert,
    because the run is already longer than the persistence.
    """
    zc = [c for c in g.columns if c.startswith("z_")]
    zs = [c for c in g.columns if c.startswith("zs_")]
    Z = g[zc].abs().fillna(0.0).to_numpy()
    S = g[zs].fillna(0.0).to_numpy() if zs else np.zeros((len(g), 1))
    zmax = np.maximum(Z.max(axis=1), S.max(axis=1) / 2.0)
    steady = g["steady"].to_numpy()
    gap = g["gap"].to_numpy().astype(bool)
    fl = [c for c in g.columns if c.startswith("flat_")]
    flat = (g[fl].fillna(False).astype(bool).any(axis=1).to_numpy() & steady) if fl else np.zeros(len(g), dtype=bool)
    return {"dev": steady & (zmax > k) & ~gap, "gap": gap, "stuck": flat & ~gap}


def alerts_from_flags(g: pd.DataFrame, flags: dict[str, np.ndarray], persist: dict[str, int], diag: Callable[[int, str], dict | None], source: str) -> list[dict]:
    """Like `alerts_from_flag`, with a separate run counter, persistence and diagnosis per reason. `diag(j, reason)` may return None."""
    rows, run, last = [], {r: 0 for r in flags}, {}
    for j in range(len(g)):
        for reason, f in flags.items():
            run[reason] = run[reason] + 1 if f[j] else 0
            p = persist[reason]
            if run[reason] == p or (run[reason] > p and (run[reason] - p) % REPEAT_EVERY_MIN == 0):
                d = diag(j, reason)
                if d is None:
                    continue
                t = g["window_start_utc"].iloc[j] + pd.Timedelta(minutes=1)
                if d["fault_type"] not in last or t - last[d["fault_type"]] > REFRACTORY:
                    rows.append({"asset_id": g["asset_id"].iloc[j], "alert_time_utc": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                 "event_class": d["event_class"], "fault_type": d["fault_type"], "confidence": float(d["confidence"]),
                                 "evidence": f"{source}: {d['evidence']}", "recommended_action": d["action"],
                                 "rule": d.get("rule", "model"), "alternatives": json.dumps(d.get("alternatives", []))})
                    last[d["fault_type"]] = t
    return sorted(rows, key=lambda r: r["alert_time_utc"])
