import json

import pandas as pd
import pytest

from watchkeeper.business_case import ASSUME, build, evaluate


def _base(**kw):
    p = {k: v[0] for k, v in ASSUME.items()}
    p.update(caught=0.889, false_per_day=0.071, repeat_per_day=0.0, false_alert_cost_eur=120.0)
    return dict(p, **kw)


def test_arithmetic_reproduces_the_organizers_published_worked_example():
    """RETROFIT_FEASIBILITY.md section 5: benefit EUR 8,268, alert handling EUR 3,110, net EUR 4,458, payback 1.0 year."""
    r = evaluate(_base())
    assert r["benefit"] == pytest.approx(8268, abs=1)
    assert r["nuisance"] == pytest.approx(3110, abs=1)
    assert r["net"] == pytest.approx(4458, abs=2)
    assert r["payback_yr"] == pytest.approx(1.0, abs=0.05)


def test_no_downtime_cost_and_few_events_never_pays_back():
    r = evaluate(_base(downtime_cost_eur_h=0.0, events_per_year=0.3))
    assert r["net"] < 0 and r["payback_yr"] == float("inf")


def test_more_false_alerts_always_lower_the_net_effect():
    assert evaluate(_base(false_per_day=0.3))["net"] < evaluate(_base(false_per_day=0.1))["net"]


def test_build_uses_the_measured_numbers_and_counts_from_the_files(tmp_path):
    metrics = {"leave_one_asset_out": {"event_recall": 0.8, "early_warning_rate": 0.5, "false_alert_episodes": 3, "excess_repeat_episodes": 2,
                                       "false_alerts_per_asset_day": 0.1, "asset_days": 50.0, "events_scored": 4}}
    (tmp_path / "m.json").write_text(json.dumps(metrics))
    pd.DataFrame({"event_id": list("abcd"), "asset_id": ["PUMP-01"] * 2 + ["PUMP-03"] * 2, "detected": [True, True, True, False],
                  "type_correct": [True, False, True, False], "lead_time_to_deadline_h": [10.0, -1.0, None, None]}).to_csv(tmp_path / "pe.csv", index=False)
    pd.DataFrame({"asset_id": ["PUMP-01", "PUMP-03"], "instrumentation_tier": ["T1_RETROFIT", "T0_LEGACY"]}).to_csv(tmp_path / "assets.csv", index=False)
    text = build(tmp_path / "m.json", tmp_path / "pe.csv", tmp_path / "assets.csv")
    assert "0.50" in text and "(2 of 4)" in text and "1 were caught before it" in text and "10.0 h" in text
    assert "0.060" in text and "0.040" in text                   # 3 and 2 episodes over 50 pump-days
