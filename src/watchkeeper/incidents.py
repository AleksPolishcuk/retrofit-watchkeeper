"""One problem is one incident. Alerts of the same family on the same pump, close in time, update one incident.

The scorer still counts every emitted alert, so grouping is for the operator view. `assign_incidents` adds an id to each alert and keeps all of them;
`incident_summary` gives one row per incident. Families: see diagnose.knowledge.FAMILY. Instrument faults group by affected channel.
"""
from __future__ import annotations

import re

import pandas as pd

from .diagnose.knowledge import FAMILY

GAP = pd.Timedelta(hours=12)
_CH = re.compile(r"([a-z0-9_]+)(?: z=| deviates alone| frozen| spread)")


def family_key(fault_type: str, evidence: str) -> str:
    fam = FAMILY.get(fault_type, "unknown")
    if fam == "instrument":
        m = _CH.search(str(evidence).split(": ", 1)[-1])
        return f"instrument:{m.group(1) if m else '?'}"
    return fam


def assign_incidents(pred: pd.DataFrame) -> pd.DataFrame:
    """Add `incident_id` (and keep alert order). Alerts of one family less than 12 h after the previous alert of that incident join it."""
    if pred.empty:
        return pred.assign(incident_id=pd.Series(dtype=str))
    out = pred.copy()
    out["t_"] = pd.to_datetime(out["alert_time_utc"], utc=True)
    out = out.sort_values(["asset_id", "t_"], kind="stable")
    ids, open_, count = [], {}, {}
    for r in out.itertuples():
        key = (r.asset_id, family_key(r.fault_type, r.evidence))
        cur = open_.get(key)
        if cur is None or r.t_ - cur[1] > GAP:
            count[r.asset_id] = count.get(r.asset_id, 0) + 1
            cur = (f"{r.asset_id}-INC{count[r.asset_id]:02d}", r.t_)
        open_[key] = (cur[0], r.t_)
        ids.append(cur[0])
    out["incident_id"] = ids
    return out.drop(columns="t_")


def incident_summary(pred: pd.DataFrame) -> pd.DataFrame:
    """One row per incident: pump, first and last alert, how many alerts, the best-supported type and its confidence."""
    p = assign_incidents(pred)
    if p.empty:
        return pd.DataFrame(columns=["incident_id", "asset_id", "first_alert_utc", "last_alert_utc", "alerts", "fault_type", "confidence", "event_class"])
    rows = []
    for iid, g in p.groupby("incident_id", sort=False):
        best = g.sort_values("confidence", ascending=False).iloc[0]
        rows.append({"incident_id": iid, "asset_id": best.asset_id, "first_alert_utc": g.alert_time_utc.min(), "last_alert_utc": g.alert_time_utc.max(),
                     "alerts": len(g), "fault_type": best.fault_type, "confidence": float(best.confidence), "event_class": best.event_class})
    return pd.DataFrame(rows).sort_values("first_alert_utc").reset_index(drop=True)
