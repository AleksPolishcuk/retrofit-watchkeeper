import numpy as np
import pandas as pd

from watchkeeper.features.causal import hold_sparse, thermal_warmup


def _frame(mode, n=None):
    n = n or len(mode)
    return pd.DataFrame({"asset_id": ["P"] * n, "operating_mode": mode, "running_fraction": [1.0 if m == "RUNNING" else 0.0 for m in mode],
                         "z_wt": np.full(n, -15.0), "z_bt": np.full(n, -8.0), "z_pd": np.full(n, 3.0), "zs_wt": np.full(n, 2.0)})


def test_thermal_channels_are_blank_for_the_first_hour_after_a_restart_only():
    mode = ["LOCKED_OUT"] * 5 + ["RUNNING"] * 200
    out = thermal_warmup(_frame(mode), 60)
    assert out["z_wt"].iloc[5:64].isna().all() and out["z_bt"].iloc[5:64].isna().all()      # the first 59 running minutes
    assert out["z_wt"].iloc[64:].notna().all()                                              # warm again from the 60th
    assert out["z_pd"].notna().all()                                                         # pressure is not thermal
    assert thermal_warmup(_frame(mode), 0)["z_wt"].notna().all()                              # off by default for the baselines


def test_a_second_restart_blanks_the_thermal_channels_again():
    mode = ["RUNNING"] * 100 + ["STOPPED"] * 3 + ["RUNNING"] * 100
    out = thermal_warmup(_frame(mode), 60)
    assert out["z_wt"].iloc[100:162].isna().all()                   # stopped minutes and the first 59 after the restart
    assert out["z_wt"].iloc[162:].notna().all()
    assert out["z_wt"].iloc[70:100].notna().all()


def test_thermal_warmup_never_looks_ahead():
    mode = ["RUNNING"] * 30 + ["STOPPED"] * 5 + ["RUNNING"] * 100
    full = thermal_warmup(_frame(mode), 60)
    cut = thermal_warmup(_frame(mode[:80]), 60)
    assert full["z_wt"].iloc[:80].isna().equals(cut["z_wt"].isna())


def test_hold_sparse_carries_a_report_forward_for_a_limited_time_and_never_backwards():
    n = 20
    f = pd.DataFrame({"asset_id": ["P"] * n, "vibration_rms_mm_s__mean": [np.nan] * n, "motor_current_a__mean": np.arange(n, dtype=float)})
    f.loc[3, "vibration_rms_mm_s__mean"] = 1.5
    f.loc[12, "vibration_rms_mm_s__mean"] = 2.5
    assets = pd.DataFrame({"asset_id": ["P"], "wireless_update_s": [300.0]})
    v = hold_sparse(f, assets, limit=6)["vibration_rms_mm_s__mean"].to_numpy()
    assert np.isnan(v[:3]).all()                                   # nothing before the first report
    assert (v[3:10] == 1.5).all() and np.isnan(v[10:12]).all()      # six minutes of holding, then a gap
    assert (v[12:18] == 2.5).all()
    assert (hold_sparse(f, assets, 6)["motor_current_a__mean"] == f["motor_current_a__mean"]).all()    # dense channels untouched


def test_wired_pumps_are_not_touched_by_the_hold():
    f = pd.DataFrame({"asset_id": ["W"] * 6, "vibration_rms_mm_s__mean": [1.0, np.nan, np.nan, np.nan, np.nan, np.nan]})
    assets = pd.DataFrame({"asset_id": ["W"], "wireless_update_s": [np.nan]})
    assert hold_sparse(f, assets, 6)["vibration_rms_mm_s__mean"].isna().sum() == 5


def test_a_regime_first_seen_after_the_baseline_is_learned_before_it_is_judged():
    """Organizer fallback: an unseen speed bin is compared with all baseline bins, so a healthy demand change gives z of 20 for days. Here it gets NaN, then ~0."""
    import numpy as np
    from watchkeeper.features.causal import regime_learning_z
    rng = np.random.default_rng(0)
    n = 24 * 60 * 5
    reg = np.where(np.arange(n) < 2 * 24 * 60, 18, 19)                          # day 3 on, the drive runs one speed bin higher
    vals = np.where(reg == 18, 40.0, 51.0) + rng.normal(0, 0.5, n)
    steady = np.ones(n, dtype=bool)
    z = regime_learning_z(vals, reg, steady, floor=0.2)
    new = np.flatnonzero(reg == 19)
    assert np.isnan(z[new[:120]]).all()                                        # nothing is judged while the regime has fewer than 120 steady minutes
    assert np.nanmax(np.abs(z[new])) < 6                                        # no bogus 20-sigma values
    assert abs(np.nanmedian(z[new[300:]])) < 0.5                                # judged against its own baseline
    assert np.nanmax(np.abs(z[: 2 * 24 * 60][np.arange(2 * 24 * 60) >= 60])) < 6


def test_regime_learning_z_is_causal_and_still_sees_a_real_fault_in_a_learned_regime():
    import numpy as np
    from watchkeeper.features.causal import regime_learning_z
    rng = np.random.default_rng(1)
    n = 24 * 60 * 4
    reg = np.where(np.arange(n) < 24 * 60 * 2, 18, 19)
    vals = np.where(reg == 18, 40.0, 51.0) + rng.normal(0, 0.5, n)
    vals[3 * 24 * 60:] += 8.0                                                  # a real +8 kW shift on day 4, in the learned regime
    steady = np.ones(n, dtype=bool)
    full = regime_learning_z(vals, reg, steady, floor=0.2)
    assert np.nanmedian(full[3 * 24 * 60 + 120:]) > 8                           # 8 kW at MAD-scaled 0.5 noise is a large z: still detected
    cut = 2 * 24 * 60 + 400
    part = regime_learning_z(vals[:cut], reg[:cut], steady[:cut], floor=0.2)
    assert np.allclose(full[:cut], part, equal_nan=True)                        # truncation does not change earlier values


def test_context_is_joined_by_time_and_pump_and_leaves_missing_pumps_alone(tmp_path):
    import pandas as pd
    from watchkeeper.features.ctxjoin import attach_context
    feat = pd.DataFrame({"asset_id": ["A", "A", "B"], "window_start_utc": ["2025-01-01T00:00:00Z", "2025-01-01T00:01:00Z", "2025-01-01T00:00:00Z"], "x": [1, 2, 3]})
    ctx = pd.DataFrame({"asset_id": ["A", "A"], "timestamp_utc": ["2025-01-01T00:00:00Z", "2025-01-01T00:01:00Z"], "duty_demand_pct": [50.0, 60.0],
                        "supply_water_temp_c": [10.0, 11.0], "ambient_temp_c": [20.0, 21.0], "sea_temp_c": [None, None]})
    p = tmp_path / "operating_context.csv"
    ctx.to_csv(p, index=False)
    out = attach_context(feat, p)
    assert list(out["x"]) == [1, 2, 3]                                          # row order and content are kept
    assert list(out["ctx_duty_demand_pct"].iloc[:2]) == [50.0, 60.0] and out["ctx_duty_demand_pct"].iloc[2] != out["ctx_duty_demand_pct"].iloc[2]   # pump B has no context: NaN
    assert attach_context(feat, tmp_path / "missing.csv") is feat               # no file, no change


def test_context_features_look_only_backwards():
    import numpy as np
    import pandas as pd
    from watchkeeper.features.causal import CTX_FEATURES, build_features
    n = 400
    rng = np.random.default_rng(0)
    g = pd.DataFrame({"asset_id": ["P"] * n, "window_start_utc": pd.date_range("2025-01-01", periods=n, freq="1min", tz="UTC"), "steady": True, "rows": 60,
                      "operating_mode": "RUNNING", "speed_ratio": 0.9, "ctx_duty_demand_pct": np.r_[np.full(200, 50.0), np.full(200, 80.0)],
                      "ctx_supply_water_temp_c": rng.normal(20, 1, n), "ctx_ambient_temp_c": rng.normal(30, 1, n)})
    g["gap"] = False
    assets = pd.DataFrame({"asset_id": ["P"], "channels_available": ["motor_speed_rpm"]})
    full = build_features(g, assets, ctx_feat=True)
    cut = build_features(g.iloc[:250].reset_index(drop=True), assets, ctx_feat=True)
    assert set(CTX_FEATURES) <= set(full.columns)
    assert np.allclose(full[CTX_FEATURES].iloc[:250].to_numpy(), cut[CTX_FEATURES].to_numpy())      # cutting the future changes nothing before the cut
    assert full["ctx_dd30"].iloc[215] > 0.2 and full["ctx_dd30"].iloc[100] == 0                    # the demand step at minute 200 shows up in the 30 minute change
    assert full["ctx_dd180"].iloc[300] > 0.2                                                       # and stays visible for three hours
    assert not set(CTX_FEATURES) & set(build_features(g, assets).columns)                           # off by default
