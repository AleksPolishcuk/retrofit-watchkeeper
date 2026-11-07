import numpy as np
import pandas as pd

from watchkeeper.detect.alerting import alerts_from_flags, split_flags


def _g(n):
    return pd.DataFrame({"asset_id": ["P"] * n, "window_start_utc": pd.date_range("2025-01-01", periods=n, freq="1min", tz="UTC"),
                         "steady": np.ones(n, dtype=bool), "gap": np.zeros(n, dtype=bool), "z_pd": np.zeros(n)})


def _diag(j, reason):
    ft = {"dev": "BEARING_WEAR", "gap": "COMMUNICATION_LOSS", "stuck": "SENSOR_STUCK"}[reason]
    return {"event_class": "SENSOR" if reason != "dev" else "MACHINE", "fault_type": ft, "confidence": 0.5, "evidence": reason, "action": "x"}


def test_a_gateway_outage_inside_a_long_deviation_still_raises_its_own_alert():
    """Regression: with one shared flag the outage never alerted, because the deviation had already been running for longer than the persistence."""
    g = _g(400)
    g["z_pd"] = 9.0                                     # deviating for the whole window
    g.loc[200:260, "gap"] = True                         # a gateway outage starts after 200 minutes of deviation
    rows = alerts_from_flags(g, split_flags(g, 6.0), {"dev": 12, "gap": 8, "stuck": 12}, _diag, "t")
    kinds = [r["fault_type"] for r in rows]
    assert "COMMUNICATION_LOSS" in kinds and "BEARING_WEAR" in kinds


def test_each_reason_has_its_own_persistence():
    g = _g(100)
    g.loc[10:19, "z_pd"] = 9.0                            # 10 minutes of deviation
    g.loc[40:50, "gap"] = True                            # 11 minutes of outage
    rows = alerts_from_flags(g, split_flags(g, 6.0), {"dev": 12, "gap": 8, "stuck": 12}, _diag, "t")
    assert [r["fault_type"] for r in rows] == ["COMMUNICATION_LOSS"]      # 10 minutes is below 12, but 11 is above the gap threshold of 8


def test_alerts_are_causal_in_time_order_and_repeat_only_every_twelve_hours():
    g = _g(1000)
    g["z_pd"] = 9.0
    rows = alerts_from_flags(g, split_flags(g, 6.0), {"dev": 12, "gap": 8, "stuck": 12}, _diag, "t")
    assert len(rows) == 1                                               # the 12 h reminder falls exactly on the limit and is held back
    g2 = _g(1600)
    g2["z_pd"] = 9.0
    rows2 = alerts_from_flags(g2, split_flags(g2, 6.0), {"dev": 12, "gap": 8, "stuck": 12}, _diag, "t")
    times = [r["alert_time_utc"] for r in rows2]
    assert times == sorted(times) and len(rows2) == 2                   # the next reminder, 24 h in, is allowed
