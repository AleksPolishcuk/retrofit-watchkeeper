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
    + [f"has_{k}" for k in KEYS] + ["flat_any", "gap", "speed_ratio"]
)


def causal_zscores(f: pd.DataFrame, baseline_h: int = 24, min_steady: int = 120) -> pd.DataFrame:
    """`f` is the output of `retrofit_sim.baselines.regime_frame`."""
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
            g["z_" + k] = z
            if s_col in g:
                g["zs_" + k] = zs
                g["flat_" + k] = (g[s_col] == 0) & g[f"{col}__count"].ge(30)
        g["gap"] = g["rows"] < 30
        out.append(g)
    return pd.concat(out, ignore_index=True)


def build_features(zf: pd.DataFrame, assets: pd.DataFrame) -> pd.DataFrame:
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
        parts.append(X[FEATURE_COLUMNS])
    return pd.concat(parts).loc[zf.index]
