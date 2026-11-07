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
