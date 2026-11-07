"""Causal regime-normalised deviations.

The organizer baseline takes its commissioning baseline from the first 24 h of the window, so an alert raised inside
that period uses statistics computed from later data. Here the baseline is an expanding one: the minutes of hour h use
only steady-running minutes from before hour h. After 24 h the baseline is frozen. Until `min_steady` steady minutes
exist there are no z-scores (no alerts), which is the price of causality.

The per-channel formulas (regime-keyed robust median / MAD, noise floors) follow the organizer's `retrofit_sim.baselines.zscores`
(MIT licensed), changed only to make the baseline causal.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from retrofit_sim import baselines as B

CH = B.CH
FLOOR = {"v": 0.05, "a": 0.01, "c": 0.05, "bt": 0.3, "ps": 1.0, "pd": 2.0, "i": 0.3, "pw": 0.2, "q": 2.0,
         "n": 5.0, "wt": 0.5, "tf": 0.3, "vp": 0.5}
KEYS = list(CH)                                   # v a c bt ps pd i pw q n wt tf vp
FEATURE_COLUMNS = (
    [f"z_{k}" for k in KEYS] + [f"zs_{k}" for k in KEYS] + [f"m15_{k}" for k in KEYS] + [f"d30_{k}" for k in KEYS]
    + [f"has_{k}" for k in KEYS] + ["flat_any", "gap", "speed_ratio", "since_lockout_h"]
)


SPARSE_CHANNELS = ("vibration_rms_mm_s", "vibration_accel_rms_g", "vibration_crest_factor", "bearing_temp_c")
THERMAL_KEYS = ("wt", "bt", "tf")


def hold_sparse(f: pd.DataFrame, assets: pd.DataFrame, limit: int = 6) -> pd.DataFrame:
    """Carry the last report of a battery wireless sensor forward for up to `limit` minutes (looking backwards only).

    A T1 pump reports vibration and bearing temperature every 5 minutes, so on the 1-minute grid only about one minute in five has a value and a
    trigger that needs 15 minutes in a row can never fire on it. Holding the last report makes the channel continuous without using the future.
    """
    wireless = set(assets.loc[assets["wireless_update_s"].notna(), "asset_id"]) if "wireless_update_s" in assets else set()
    out = f.copy()
    for a in wireless & set(out["asset_id"]):
        m = (out["asset_id"] == a).to_numpy()
        for c in SPARSE_CHANNELS:
            col = f"{c}__mean"
            if col in out:
                out.loc[m, col] = out.loc[m, col].ffill(limit=limit).to_numpy()
    return out


def thermal_warmup(zf: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """After a restart the motor and bearing are still cold, which looks like a large negative deviation. Blank the thermal channels until the pump
    has run `minutes` in a row. Causal: only the past run length is used."""
    if minutes <= 0:
        return zf
    out = zf.copy()
    run = ((out["operating_mode"] == "RUNNING") & (out["running_fraction"] >= 0.99)).to_numpy()
    age = np.zeros(len(out), dtype=int)
    for _, idx in out.groupby("asset_id").indices.items():
        r = run[idx]
        grp = np.cumsum(~r)
        age[idx] = pd.Series(r.astype(int)).groupby(grp).cumsum().to_numpy()
    young = age < minutes
    for k in THERMAL_KEYS:
        for pre in ("z_", "zs_"):
            if pre + k in out:
                out.loc[young, pre + k] = np.nan
    return out


def regime_learning_z(vals: np.ndarray, reg: np.ndarray, steady: np.ndarray, floor: float, base_end: int = 1440, min_regime: int = 120, learn_min: int = 180) -> np.ndarray:
    """Robust z against a baseline that belongs to the operating regime (speed bin) the minute is in, and only to that regime.

    The organizer baseline falls back to the median of *all* baseline regimes when a regime was not seen during the first 24 h. A drive that later settles
    at a new speed (a demand change, not a fault) then gets z values of 20 or more for hours. Here a regime without enough baseline gets no z-score at all
    (NaN, so no alert) until it has `min_regime` steady minutes; its baseline is then frozen after `learn_min` minutes. Regimes seen in the first
    `base_end` minutes keep the expanding baseline of the first 24 h, as before. Hourly checkpoints; a minute uses only minutes before its own hour.
    """
    n = len(vals)
    z = np.full(n, np.nan)
    hour = np.arange(n) // 60
    ok = steady & ~np.isnan(vals)
    for r in np.unique(reg):
        idx = np.flatnonzero(reg == r)
        base_idx = idx[ok[idx]]
        if len(base_idx) < min_regime:
            continue
        end = base_end if int((base_idx < base_end).sum()) >= min_regime else int(base_idx[min(learn_min, len(base_idx)) - 1]) + 1
        hours_here = hour[idx]
        for hh in np.unique(hours_here):
            pre = base_idx[base_idx < min(60 * int(hh), end)]
            if len(pre) < min_regime:
                continue
            b = vals[pre]
            med = np.median(b)
            mad = np.median(np.abs(b - med))
            sel = idx[hours_here == hh]
            z[sel] = (vals[sel] - med) / max(1.4826 * mad, floor)
    return z


def causal_zscores(f: pd.DataFrame, baseline_h: int = 24, min_steady: int = 120, thermal_min: int = 0, learn: bool = False, min_regime: int = 120, learn_min: int = 180, tf_adj: bool = False) -> pd.DataFrame:
    """`f` is the output of `retrofit_sim.baselines.regime_frame`. With `learn=True` the level baseline is per regime and regimes first seen after the
    baseline period are learned before they are judged (see `regime_learning_z`)."""
    out = []
    for _, g in f.groupby("asset_id", sort=False):
        g = g.copy().reset_index(drop=True)
        t0 = g["window_start_utc"].min()
        hour = ((g["window_start_utc"] - t0).dt.total_seconds() // 3600).astype(int).clip(upper=baseline_h).to_numpy()
        for k, col in CH.items():
            m, s_col = f"{col}__mean", f"{col}__std"
            if m not in g or g[m].notna().sum() == 0:
                g["z_" + k] = np.nan
                continue
            z = np.full(len(g), np.nan)
            zs = np.full(len(g), np.nan)
            for h in range(1, baseline_h + 1):
                sel = hour == h
                if not sel.any():
                    continue
                base = g[(g["window_start_utc"] < t0 + pd.Timedelta(hours=h)) & g["steady"]]
                if len(base) < min_steady:
                    continue
                med = base.groupby("regime")[m].median()
                mad = base.groupby("regime")[m].apply(lambda s: (s - s.median()).abs().median())
                gm, gmad = base[m].median(), (base[m] - base[m].median()).abs().median()
                reg = g.loc[sel, "regime"]
                sd = 1.4826 * reg.map(mad).fillna(gmad)
                z[sel] = ((g.loc[sel, m] - reg.map(med).fillna(gm)) / np.maximum(sd, FLOOR[k])).to_numpy()
                if s_col in g:
                    sb = base[s_col].median()
                    zs[sel] = ((g.loc[sel, s_col] - sb) / max(1.4826 * (base[s_col] - sb).abs().median(), 1e-3 + 0.05 * abs(sb))).to_numpy()
            if learn:
                vals = g[m].to_numpy(dtype=float)
                if tf_adj and k == "tf" and "ctx_supply_water_temp_c" in g:
                    vals = vals - g["ctx_supply_water_temp_c"].to_numpy(dtype=float)       # fluid temperature relative to the supply water temperature from the operating context
                z = regime_learning_z(vals, g["regime"].to_numpy(), g["steady"].to_numpy().astype(bool), FLOOR[k], baseline_h * 60, min_regime, learn_min)
            g["z_" + k] = z
            if s_col in g:
                g["zs_" + k] = zs
                g["flat_" + k] = (g[s_col] == 0) & g[f"{col}__count"].ge(30)
        g["gap"] = g["rows"] < 30
        out.append(g)
    return thermal_warmup(pd.concat(out, ignore_index=True), thermal_min)


def _hours_since_lockout(mode: np.ndarray, n: int, cap: float = 99.0) -> np.ndarray:
    """Hours since the last minute in LOCKED_OUT (maintenance), looking backwards only. Misalignment and calibration offsets
    often appear right after maintenance. `cap` when there has been no lockout yet."""
    out = np.full(n, cap)
    if len(mode) != n:
        return out
    last = None
    for j in range(n):
        if mode[j] == "LOCKED_OUT":
            last = j
        if last is not None:
            out[j] = min((j - last) / 60.0, cap)
    return out


CTX_FEATURES = ["ctx_demand", "ctx_dd30", "ctx_dd180", "ctx_temp", "ctx_amb"]


def build_features(zf: pd.DataFrame, assets: pd.DataFrame, ctx_feat: bool = False) -> pd.DataFrame:
    """Feature matrix aligned with `zf`. Rolling terms look backwards only. Channel availability comes from assets.csv."""
    avail = {r.asset_id: set(str(r.channels_available).split("|")) for r in assets.itertuples()}
    parts = []
    for a, g in zf.groupby("asset_id", sort=False):
        X = pd.DataFrame(index=g.index)
        for k in KEYS:
            z = g[f"z_{k}"] if f"z_{k}" in g else pd.Series(np.nan, index=g.index)
            zs = g[f"zs_{k}"] if f"zs_{k}" in g else pd.Series(np.nan, index=g.index)
            X[f"z_{k}"] = z.fillna(0.0).clip(-50, 50)
            X[f"zs_{k}"] = zs.fillna(0.0).clip(-50, 50)
            X[f"m15_{k}"] = X[f"z_{k}"].rolling(15, min_periods=1).mean()
            X[f"d30_{k}"] = (X[f"z_{k}"] - X[f"z_{k}"].shift(30)).fillna(0.0)
            X[f"has_{k}"] = float(CH[k] in avail.get(a, set()))
        fl = [c for c in g.columns if c.startswith("flat_")]
        X["flat_any"] = (g[fl].fillna(False).astype(bool).any(axis=1) & g["steady"]).astype(float) if fl else 0.0
        X["gap"] = g["gap"].astype(float)
        X["speed_ratio"] = g["speed_ratio"].fillna(-1.0) if "speed_ratio" in g else -1.0
        X["since_lockout_h"] = _hours_since_lockout(g["operating_mode"].to_numpy() if "operating_mode" in g else np.array([]), len(g))
        if ctx_feat:
            # operating context as extra evidence for the classifier: a recent change of cooling demand makes a deviation more likely to be benign
            if "ctx_duty_demand_pct" in g:
                d = g["ctx_duty_demand_pct"].astype(float).ffill().fillna(0.0) / 100.0         # forward fill only: causal
                X["ctx_demand"] = d
                dd = (d - d.shift(30)).abs().fillna(0.0)
                X["ctx_dd30"] = dd
                X["ctx_dd180"] = dd.rolling(180, min_periods=1).max()
                X["ctx_temp"] = g["ctx_supply_water_temp_c"].astype(float).ffill().fillna(0.0) / 50.0 if "ctx_supply_water_temp_c" in g else 0.0
                X["ctx_amb"] = g["ctx_ambient_temp_c"].astype(float).ffill().fillna(0.0) / 50.0 if "ctx_ambient_temp_c" in g else 0.0
            else:
                for col in CTX_FEATURES:
                    X[col] = 0.0
        parts.append(X[FEATURE_COLUMNS + (CTX_FEATURES if ctx_feat else [])])
    return pd.concat(parts).loc[zf.index]
