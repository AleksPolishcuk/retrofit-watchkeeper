import numpy as np
import pandas as pd

from watchkeeper.detect.signature import fused_flag, fused_type, signature_scores, slow_detect, slow_flag


def _g(n, seed=0):
    rng = np.random.default_rng(seed)
    g = pd.DataFrame({"asset_id": ["P"] * n, "window_start_utc": pd.date_range("2025-01-01", periods=n, freq="1min", tz="UTC"),
                      "steady": np.ones(n, dtype=bool), "gap": np.zeros(n, dtype=bool)})
    for k in ("ps", "n", "pw", "q", "pd", "i", "v", "a", "c", "bt", "wt"):
        g[f"z_{k}"] = rng.normal(0, 1, n)
    return g


def _ramp(g, start, per_min, sig):
    for k, s in sig.items():
        g.loc[start:, f"z_{k}"] += s * per_min * np.arange(len(g) - start)
    return g


def test_fusion_alarms_before_any_single_channel_reaches_the_single_channel_threshold():
    g = _ramp(_g(3000), 500, 0.003, {"ps": -1, "n": 1, "pw": 1, "q": -1})         # four channels drift by 0.003 sigma per minute
    single = np.flatnonzero((g[["z_ps", "z_n", "z_pw", "z_q"]].abs() > 6).any(axis=1).to_numpy())
    fused = np.flatnonzero(fused_flag(g, 5.0))
    assert len(fused) and fused[0] < single[0] - 200                                # the fused score crosses 5 well before any channel crosses 6
    assert fused_type(g).iloc[fused[0]] == "SUCTION_STRAINER_CLOGGING"


def test_healthy_noise_does_not_trigger_the_fused_score_or_the_slow_detector():
    for seed in range(8):
        g = _g(6000, seed)
        assert not fused_flag(g, 5.0).any(), seed
        assert not slow_flag(g, 8.0).any(), seed


def test_one_channel_alone_cannot_trigger_because_the_largest_contributor_is_left_out():
    for seed in range(5):
        g = _g(1500, seed)
        g["z_ps"] = -30.0                                                            # a single huge deviation
        assert not fused_flag(g, 5.0).any(), seed
        assert not slow_flag(g, 8.0).any(), seed


def test_slow_detector_finds_a_small_persistent_shift_that_minute_thresholds_miss():
    g = _ramp(_g(8000), 1000, 0.0005, {"pd": -1, "i": -1, "q": -1, "pw": -1})        # impeller-wear-like, very slow: 3.5 sigma at the end
    assert (g[["z_pd", "z_i", "z_q", "z_pw"]].rolling(15, min_periods=1).mean().abs() < 5).all().all()      # no channel is persistently out by 5 sigma
    assert slow_flag(g, 8.0).any()


def test_the_flags_never_use_the_future():
    g = _ramp(_g(4000), 800, 0.004, {"ps": -1, "n": 1, "pw": 1, "q": -1})
    cut = 2500
    for fn in (lambda x: fused_flag(x, 5.0), lambda x: slow_flag(x, 8.0)):
        assert (fn(g)[:cut] == fn(g.iloc[:cut].reset_index(drop=True))[:cut]).all()


def test_scores_use_only_the_channels_that_exist_and_need_three():
    g = _g(50).drop(columns=["z_q"])
    sc = signature_scores(g)
    assert "SUCTION_STRAINER_CLOGGING" in sc and np.isfinite(sc["SUCTION_STRAINER_CLOGGING"]).all()
    g2 = g.drop(columns=["z_n", "z_pw"])                                             # only ps left for that signature
    assert "SUCTION_STRAINER_CLOGGING" not in signature_scores(g2)


def test_transient_and_gap_minutes_are_ignored():
    g = _ramp(_g(2000), 100, 0.01, {"ps": -1, "n": 1, "pw": 1, "q": -1})
    g["steady"] = False
    assert not fused_flag(g, 5.0).any() and not slow_flag(g, 8.0).any()


def test_slow_detector_names_the_signature_that_is_hot():
    g = _ramp(_g(8000), 1000, 0.0006, {"pd": -1, "i": -1, "q": -1, "pw": -1})
    flag, kind = slow_detect(g, 8.0)
    assert flag.any() and kind[flag][0] == "IMPELLER_WEAR"
    assert (kind[~flag] == None).all()                                              # noqa: E711
