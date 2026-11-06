from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from watchkeeper.detect.cavitation import cavitation_episodes
from watchkeeper.features.npsh import npsh_margin

DATA = Path(__file__).resolve().parents[1] / "data"


def _frame(n):
    return pd.DataFrame({"asset_id": ["PUMP-06"] * n, "window_start_utc": pd.date_range("2025-10-06", periods=n, freq="1min", tz="UTC")})


def test_alert_comes_at_the_fifth_low_minute_and_only_once_per_episode():
    m = np.full(120, 4.0)
    m[20:50] = 0.7                                         # one long episode
    alerts, active = cavitation_episodes(_frame(120), m)
    assert len(alerts) == 1
    assert alerts[0]["alert_time_utc"] == "2025-10-06T00:25:00Z"      # minute 24 (5th low minute) plus one minute
    assert active[24] and not active[10] and not active[100]


def test_short_dips_under_five_minutes_do_not_alert():
    m = np.full(60, 4.0)
    m[10:14] = 0.5                                         # 4 minutes
    assert cavitation_episodes(_frame(60), m)[0] == []


def test_gaps_shorter_than_thirty_minutes_stay_one_episode_and_longer_gaps_start_a_new_one():
    m = np.full(200, 4.0)
    m[10:20] = 0.8
    m[40:50] = 0.8                                         # 20 minutes after the first one ended: same episode
    m[120:130] = 0.8                                       # far later: new episode
    alerts, _ = cavitation_episodes(_frame(200), m)
    assert len(alerts) == 2


def test_missing_margin_is_never_low():
    assert cavitation_episodes(_frame(30), np.full(30, np.nan))[0] == []


def test_alerts_only_use_the_past():
    """Appending later minutes must not change alerts already raised."""
    m = np.full(150, 4.0)
    m[30:60] = 0.7
    full, _ = cavitation_episodes(_frame(150), m)
    cut, _ = cavitation_episodes(_frame(45), m[:45])
    assert cut == [a for a in full if a["alert_time_utc"] <= "2025-10-06T00:45:00Z"]


@pytest.mark.skipif(not (DATA / "assets.csv").exists(), reason="data pack not linked")
def test_margin_separates_cavitation_from_healthy_operation_on_dev_pumps():
    from watchkeeper.evalkit import load_dev
    d = load_dev(DATA)
    A = d.assets.set_index("asset_id")
    healthy_min = []
    for a in ("PUMP-01", "PUMP-04", "PUMP-08", "PUMP-09"):
        g = d.feat[d.feat.asset_id == a].copy().sort_values("window_start_utc")
        healthy_min.append(float(npsh_margin(g, A.loc[a]).min()))
    assert min(healthy_min) > 2.0                           # never near the 1.15 limit on pumps without cavitation

    g = d.feat[d.feat.asset_id == "PUMP-06"].copy()
    g["window_start_utc"] = pd.to_datetime(g["window_start_utc"], utc=True)
    g = g.sort_values("window_start_utc").reset_index(drop=True)
    margin = npsh_margin(g, A.loc["PUMP-06"]).to_numpy()
    alerts, _ = cavitation_episodes(g, margin)
    ev = d.events[(d.events.asset_id == "PUMP-06") & (d.events.fault_type == "CAVITATION")]
    assert len(ev) == 4
    inside = 0
    for a in alerts:
        t = pd.Timestamp(a["alert_time_utc"])
        inside += any(pd.Timestamp(e.onset_utc) <= t <= pd.Timestamp(e.end_utc) + pd.Timedelta(minutes=30) for e in ev.itertuples())
    assert inside >= 3                                       # at least three of the four labelled episodes are found
    assert len(alerts) - inside <= 1                         # and at most one alert falls outside them
