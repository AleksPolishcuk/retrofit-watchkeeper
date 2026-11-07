"""Enterprise verification scenarios (A01-A18) and pilot checks (P01-P05, P10) as tests.

Unit tests use small synthetic minute frames and always run. End-to-end tests run the frozen model on a healthy simulated fleet and need `models/wk.joblib` and
`bank/healthy` (make model, make bank); they are skipped otherwise.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from retrofit_sim import baselines as B

from watchkeeper.detect.datahealth import data_health
from watchkeeper.detect.rangecheck import check_ranges
from watchkeeper.evalkit import DevData
from watchkeeper.features.causal import causal_zscores
from watchkeeper.features.hygiene import clean_minutes

ROOT = Path(__file__).resolve().parents[1]
CHANNELS = ["motor_speed_rpm", "motor_current_a", "motor_power_kw", "suction_pressure_kpa", "discharge_pressure_kpa", "flow_m3_h", "fluid_temp_c", "bearing_temp_c", "motor_winding_temp_c"]
BASE = {"motor_speed_rpm": 1480.0, "motor_current_a": 70.0, "motor_power_kw": 40.0, "suction_pressure_kpa": 60.0, "discharge_pressure_kpa": 420.0, "flow_m3_h": 300.0,
        "fluid_temp_c": 22.0, "bearing_temp_c": 55.0, "motor_winding_temp_c": 80.0}
ASSET = pd.Series({"asset_id": "P", "channels_available": "|".join(CHANNELS), "wireless_update_s": 0, "motor_rated_rpm": 1480, "motor_rated_kw": 45.0,
                   "motor_rated_current_a": 82.0, "design_flow_m3_h": 320.0, "design_head_m": 45.0})


def frame(n=600, seed=0):
    rng = np.random.default_rng(seed)
    f = pd.DataFrame({"asset_id": "P", "window_start_utc": pd.date_range("2025-01-01", periods=n, freq="1min", tz="UTC"), "rows": 60, "operating_mode": "RUNNING",
                      "running_fraction": 1.0, "quality_any": 0})
    for ch, v in BASE.items():
        f[f"{ch}__mean"] = v + rng.normal(0, 0.003 * v, n)
        f[f"{ch}__std"] = 0.002 * v + rng.random(n) * 0.001 * v
        f[f"{ch}__count"] = 60
    return f


def blank(f, ch, start, end=None):
    f = f.copy()
    sl = f.index[start:end]
    f.loc[sl, f"{ch}__mean"] = np.nan
    f.loc[sl, f"{ch}__std"] = np.nan
    f.loc[sl, f"{ch}__count"] = 0
    return f


# ---- A14, P04: repeated and reordered minutes -------------------------------------------------------------------------------------------------------------------
def test_a14_a_repeated_minute_is_dropped_and_a_conflicting_one_is_counted():
    f = frame(100)
    same = pd.concat([f.iloc[:50], f.iloc[49:50], f.iloc[50:]]).reset_index(drop=True)
    cleaned, rep = clean_minutes(same)
    assert len(cleaned) == 100 and rep["duplicates_dropped"] == 1 and rep["conflicts"] == 0
    other = f.iloc[49:50].copy()
    other["flow_m3_h__mean"] = 999.0
    conflicting = pd.concat([f.iloc[:50], other, f.iloc[50:]]).reset_index(drop=True)
    cleaned, rep = clean_minutes(conflicting)
    assert len(cleaned) == 100 and rep["conflicts"] == 1
    assert cleaned.loc[cleaned.window_start_utc == f.window_start_utc.iloc[49], "flow_m3_h__mean"].iloc[0] == 999.0      # the last delivered value is kept
    assert not cleaned.window_start_utc.duplicated().any()


def test_p04_clean_input_is_returned_untouched_and_disorder_is_counted():
    f = frame(100)
    cleaned, rep = clean_minutes(f)
    assert cleaned is f and rep["duplicates_dropped"] == 0 and rep["out_of_order"] == 0
    shuffled = pd.concat([f.iloc[50:], f.iloc[:50]]).reset_index(drop=True)
    assert clean_minutes(shuffled)[1]["out_of_order"] >= 1


def test_a14_the_regime_frame_no_longer_crashes_on_a_repeated_minute():
    from watchkeeper.methods import _regime
    f = frame(300)
    dup = pd.concat([f.iloc[:150], f.iloc[149:150], f.iloc[150:]]).reset_index(drop=True)
    assets = pd.DataFrame([ASSET])
    rf = _regime(DevData(Path("."), assets, dup, pd.DataFrame(columns=["asset_id"]), pd.DataFrame(), pd.DataFrame(), cache={}))
    assert len(rf) == 300


# ---- data health: A01, A02, A03, A04, A09, A13, A18, P02, P03 -------------------------------------------------------------------------------------------------
def test_a01_clean_data_is_ok():
    h = data_health(frame(400), ASSET)
    assert h["status"] == "OK" and all(c["status"] == "live" for c in h["channels"])


def test_a02_a_twelve_minute_silence_is_reported_but_not_before_it_happened():
    f = frame(260).drop(index=range(200, 212)).reset_index(drop=True)        # the silence ended 48 minutes before the end of the window
    after = data_health(f, ASSET)
    assert after["status"] == "DEGRADED" and any("Gateway was silent for 12 minutes" in r for r in after["reasons"])
    before = data_health(f, ASSET, as_of=f.window_start_utc.iloc[150])
    assert before["status"] == "OK" and before["gaps"] == []


def test_a03_a_lost_channel_is_named_with_the_time_it_stopped():
    f = blank(frame(500), "suction_pressure_kpa", 300)
    h = data_health(f, ASSET)
    ch = {c["name"]: c for c in h["channels"]}
    assert ch["suction_pressure_kpa"]["status"] == "missing" and ch["discharge_pressure_kpa"]["status"] == "live"
    assert h["status"] == "DEGRADED" and any(r.startswith("Suction pressure: nothing received since") for r in h["reasons"])
    early = data_health(f, ASSET, as_of=f.window_start_utc.iloc[320])
    assert {c["name"]: c["status"] for c in early["channels"]}["suction_pressure_kpa"] == "stale"


def test_a04_a_lost_speed_signal_says_that_operating_point_checks_are_suspended():
    h = data_health(blank(frame(500), "motor_speed_rpm", 400), ASSET)
    assert h["status"] == "DEGRADED" and any("Speed" in r and "suspended" in r for r in h["reasons"])


def test_a18_rows_without_any_measurement_are_insufficient_data_not_a_quiet_pump():
    f = frame(500)
    for ch in CHANNELS:
        f = blank(f, ch, 440)
    h = data_health(f, ASSET)
    assert h["status"] == "INSUFFICIENT_DATA" and "nothing can be evaluated" in h["reasons"][0]


def test_p02_no_data_at_all_for_a_while_is_reported_as_no_data():
    f = frame(300)
    h = data_health(f, ASSET, as_of=f.window_start_utc.iloc[-1] + pd.Timedelta(minutes=40))
    assert h["status"] == "NO_DATA" and "No data for" in h["reasons"][0]


def test_a09_a_new_pump_is_learning_its_normal_and_says_so():
    h = data_health(frame(60), ASSET)
    assert h["status"] == "BASELINE_LEARNING" and any("Learning this pump's normal" in r for r in h["reasons"])


def test_a13_a_start_is_announced():
    f = frame(300)
    f.loc[f.index[:295], "operating_mode"] = "STOPPED"
    h = data_health(f, ASSET)
    assert any("Pump started" in r for r in h["reasons"])


def test_a11_quality_flags_are_counted_and_named():
    f = frame(400)
    f.loc[f.index[360:380], "quality_any"] = 2
    h = data_health(f, ASSET)
    assert h["quality"]["flagged_last_60"] == 20 and h["quality"]["bits"] == {"OUT_OF_RANGE": 20}
    assert h["status"] == "DEGRADED" and any("OUT_OF_RANGE" in r for r in h["reasons"])


# ---- P05: units and tags -------------------------------------------------------------------------------------------------------------------------------------
def test_p05_a_factor_ten_current_and_psi_pressure_are_caught_and_a_normal_pump_is_not():
    assert check_ranges(frame(200), ASSET) == []
    f = frame(200)
    f["motor_current_a__mean"] *= 10
    f["discharge_pressure_kpa__mean"] *= 6.9
    ch = {i["channel"] for i in check_ranges(f, ASSET)}
    assert {"motor_current_a", "discharge_pressure_kpa"} <= ch


# ---- A12: frozen sensor ---------------------------------------------------------------------------------------------------------------------------------------
def _flat_minutes(strict, moving):
    f = frame(500)
    sl = f.index[300:340]
    f.loc[sl, "discharge_pressure_kpa__std"] = 0.0
    f.loc[sl, "discharge_pressure_kpa__mean"] = np.linspace(420.0, 423.0, 40) if moving else 421.0
    rf = B.regime_frame(f, pd.DataFrame([ASSET]))
    z = causal_zscores(rf, learn=True, flat_strict=strict)
    return int(z["flat_pd"].iloc[300:340].sum())


def test_a12_a_value_that_moves_between_minutes_is_not_frozen_when_the_strict_rule_is_on():
    assert _flat_minutes(strict=False, moving=True) == 40          # the old rule only looks at the spread inside a minute
    assert _flat_minutes(strict=True, moving=True) == 0
    assert _flat_minutes(strict=True, moving=False) >= 39          # a really frozen value is still caught


# ---- A04: lost speed ------------------------------------------------------------------------------------------------------------------------------------------
def test_a04_minutes_after_the_speed_signal_was_lost_are_not_steady_when_the_option_is_on():
    from watchkeeper.methods import _regime
    f = blank(frame(600), "motor_speed_rpm", 300, 450)
    d = DevData(Path("."), pd.DataFrame([ASSET]), f, pd.DataFrame(columns=["asset_id"]), pd.DataFrame(), pd.DataFrame(), cache={})
    plain = _regime(d)
    robust = _regime(d, 0, ("speedloss",))
    assert plain["steady"].iloc[320:450].all()                       # default: unchanged
    assert not robust["steady"].iloc[316:450].any() and robust["steady"].iloc[:300].iloc[20:].all() and robust["steady"].iloc[470:].all()


# ---- end to end on a healthy simulated fleet (frozen model) ----------------------------------------------------------------------------------------------
BANK = ROOT / "bank" / "healthy" / "s301" / "public" / "features_1min.parquet"
MODEL = ROOT / "models" / "wk.joblib"
e2e = pytest.mark.skipif(not (BANK.exists() and MODEL.exists()), reason="needs bank/healthy and models/wk.joblib")


@pytest.fixture(scope="module")
def healthy():
    from watchkeeper.bank import load_set
    from watchkeeper.diagnose import DiagnosisModel
    d = load_set("healthy", seeds=[301])
    base = d.feat[d.feat.asset_id == "B301-04"].reset_index(drop=True)
    return d.assets, base, DiagnosisModel.load(MODEL)


def _run(healthy, feat, **opts):
    from watchkeeper.methods import ROBUST, WKMethod
    assets, _, model = healthy
    d = DevData(Path("."), assets, feat.copy(), pd.DataFrame(columns=["asset_id"]), pd.DataFrame(), pd.DataFrame(), cache={})
    return WKMethod(ctx=ROBUST if opts.get("robust") else ()).predict(model, d, "B301-04")


@e2e
def test_e2e_a14_a_repeated_row_does_not_crash_the_pipeline(healthy):
    _, base, _ = healthy
    dup = pd.concat([base.iloc[:1865], base.iloc[1864:1865], base.iloc[1865:]]).reset_index(drop=True)
    assert len(_run(healthy, dup)) == len(_run(healthy, base))        # same alerts as without the repeated minute


@e2e
def test_e2e_a04_a_lost_speed_signal_raises_no_false_alerts_with_the_option(healthy):
    _, base, _ = healthy
    f = base.copy()
    for c in [c for c in f.columns if c.startswith("motor_speed_rpm__")]:
        f.loc[f.index[1860:], c] = np.nan if not c.endswith("__count") else 0
    assert len(_run(healthy, f, robust=True)) == 0
    assert len(_run(healthy, f)) > 0                                  # documents the behaviour of the default (submitted) configuration


@e2e
def test_e2e_a12_a_changing_value_is_not_called_frozen_with_the_option(healthy):
    _, base, _ = healthy
    f = base.copy()
    sl = f.index[1860:1900]
    f.loc[sl, "discharge_pressure_kpa__std"] = 0.0
    f.loc[sl, "discharge_pressure_kpa__mean"] = f.loc[sl, "discharge_pressure_kpa__mean"].to_numpy() + np.linspace(0, 3, 40)
    assert "SENSOR_STUCK" in set(_run(healthy, f).fault_type)
    assert "SENSOR_STUCK" not in set(_run(healthy, f, robust=True).fault_type)


@e2e
def test_e2e_a06_a_large_sustained_deviation_is_reported_as_unexplained_with_the_option(healthy):
    _, base, _ = healthy
    f = base.copy()
    sl = f.index[1860:1860 + 14 * 60]
    for col, k in (("flow_m3_h__mean", 0.8), ("discharge_pressure_kpa__mean", 1.12), ("motor_current_a__mean", 0.9)):
        f.loc[sl, col] = f.loc[sl, col] * k
    plain = _run(healthy, f)
    robust = _run(healthy, f, robust=True)
    assert len(plain) == 0                                            # the default stays silent: the classifier calls it normal
    assert "UNKNOWN" in set(robust.fault_type) and "persistent_unexplained" in set(robust.rule)
