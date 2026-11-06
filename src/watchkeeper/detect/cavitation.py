"""Cavitation episodes from the estimated NPSH margin.

An episode is a margin below 1.15 for at least 5 consecutive running minutes (the organizers' label definition). Low minutes
less than 30 minutes apart belong to one episode. One alert is raised when the 5th consecutive low minute is reached, and none
again for the same episode. Streaming and causal: each decision uses only the current and earlier minutes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..features.npsh import CAVITATION_MARGIN

MIN_RUN = 5
EPISODE_GAP = 30


def cavitation_episodes(g: pd.DataFrame, margin: np.ndarray) -> tuple[list[dict], np.ndarray]:
    """Return (alerts, active). `active[j]` is True while a cavitation episode has been confirmed and is not over yet
    (including the 30 minute tail), so that other alerts can be held back during it."""
    n = len(g)
    low = np.where(np.isnan(margin), False, margin < CAVITATION_MARGIN)
    active = np.zeros(n, dtype=bool)
    alerts, run, last_low, alerted = [], 0, None, False
    for j in range(n):
        if low[j]:
            if last_low is not None and j - last_low >= EPISODE_GAP:
                alerted = False                       # a new episode begins after a quiet gap
            run += 1
            last_low = j
            if run == MIN_RUN and not alerted:
                depth = float(np.nanmin(margin[j - MIN_RUN + 1: j + 1]))
                t = g["window_start_utc"].iloc[j] + pd.Timedelta(minutes=1)
                alerts.append({"asset_id": g["asset_id"].iloc[j], "alert_time_utc": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                               "event_class": "MACHINE", "fault_type": "CAVITATION",
                               "confidence": float(np.clip(0.55 + 0.4 * (CAVITATION_MARGIN - depth) / CAVITATION_MARGIN, 0.5, 0.95)),
                               "evidence": f"npsh_margin={depth:.2f}", "recommended_action": None})
                alerted = True
        else:
            run = 0
        if alerted and last_low is not None and j - last_low < EPISODE_GAP:
            active[j] = True
    return alerts, active
