"""Harness checks. They need the data pack linked at ./data (make data); otherwise they are skipped."""
import warnings
from pathlib import Path

import pandas as pd
import pytest

from watchkeeper.evalkit import empty_predictions, load_dev, run_fixed_split, run_loo, score_ids
from watchkeeper.methods import B1Method

DATA = Path(__file__).resolve().parents[1] / "data"
pytestmark = [pytest.mark.skipif(not (DATA / "assets.csv").exists(), reason="data pack not linked"),
              pytest.mark.filterwarnings("ignore::RuntimeWarning")]


@pytest.fixture(scope="module")
def dev():
    return load_dev(DATA)


def test_dev_data_has_no_test_pump(dev):
    assert set(dev.ids) == {f"PUMP-{i:02d}" for i in range(1, 10)}
    for df in (dev.feat, dev.events, dev.benign, dev.alarms):
        assert not (set(df.asset_id) & {"PUMP-10", "PUMP-11", "PUMP-12"})


def test_empty_predictions_score_only_alert_burden(dev):
    r = score_ids(empty_predictions(), dev, dev.ids)
    assert r["event_recall"] == 0.0
    assert r["composite_score"] == pytest.approx(10.0)       # only the 10 percent alert-burden term


def test_oracle_predictions_score_near_perfect(dev):
    """One correct alert at the detectable time of every observable event must score recall 1, type recall 1, no false alerts."""
    ev = dev.events[dev.events.observable.astype(str).str.lower() == "true"]
    rows = [{"asset_id": e.asset_id, "alert_time_utc": e.detectable_utc, "event_class": e.event_class, "fault_type": e.fault_type,
             "confidence": 1.0, "evidence": "oracle", "recommended_action": "n/a"} for e in ev.itertuples()]
    r = score_ids(pd.DataFrame(rows), dev, dev.ids)
    assert r["event_recall"] == 1.0
    assert r["fault_type_recall"] == 1.0
    assert r["class_recall"] == 1.0
    assert r["false_alert_episodes"] == 0
    assert r["composite_score"] > 95


def test_leave_one_asset_out_scores_all_nine_pumps(dev):
    """Regression: the LOO score once came out empty because the run label was passed as the scorer's split filter."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = run_loo(B1Method(fixed=(6, 15)), dev)
    r = res["all"]
    assert set(r["assets"]) == set(dev.ids)
    assert r["events_scored"] == 35                       # 26 on train + 9 on validation
    assert r["composite_score"] > 20


def test_b1_with_organizer_parameters_reproduces_published_scores(dev):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = run_fixed_split(B1Method(fixed=(6, 15)), dev)
    assert res["validation"]["composite_score"] == pytest.approx(78.0, abs=0.1)
    assert res["train"]["composite_score"] == pytest.approx(58.2, abs=0.1)


def test_causal_b1_does_not_change_early_alerts_when_telemetry_is_cut(dev):
    """Cuts inside and after the 24 h baseline period, on the pumps where organizer B1 changed its early alerts."""
    from watchkeeper.evalkit import check_causality
    from watchkeeper.methods import B1CausalMethod
    m = B1CausalMethod(fixed=(6, 15))
    problems = []
    for asset in ("PUMP-04", "PUMP-06"):
        problems += check_causality(m, (6, 15), dev, asset, (6, 20, 55))
    assert problems == []


def test_wk_method_is_causal_under_truncation(dev):
    """Causal baseline, backward-looking features and a model fitted before prediction: cutting the data must not change early alerts."""
    from watchkeeper.evalkit import check_causality
    from watchkeeper.methods import WKMethod
    m = WKMethod(trees=30)
    model = m.fit(dev, dev.ids_of("train"))
    problems = []
    for asset in ("PUMP-04", "PUMP-08"):
        problems += check_causality(m, model, dev, asset, (6, 20, 55))
    assert problems == []
