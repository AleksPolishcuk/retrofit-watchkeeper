"""Earlier detection by fusing channels along each fault's physical signature, then watching the fused score for slow change.

Why: a developing fault moves several channels a little at the same time, each far below a single-channel threshold. Combining them along the
expected directions improves the signal-to-noise ratio by about the square root of the number of channels, so the same false-alarm rate allows an
earlier alarm.

The fused score is *trimmed*: the single largest contributor is left out before the rest are combined. A lone channel with a huge deviation (a sensor
fault, a stuck value, a seasonal temperature swing) therefore cannot raise a machine-fault score on its own; at least two channels have to move in the
physically expected direction. Single-channel events stay with the existing per-channel trigger and the sensor rules.

Signs are from TECHNICAL_MODEL.md section 9 and START_HERE.md (what each fault does to which channel). Everything is backward looking: a score at minute t
uses only minutes up to t, and the slow detector acts on hours that are already complete.
Units: standard errors under white noise (window sum divided by the square root of the number of samples in it); real data are autocorrelated, so thresholds are
calibrated on healthy simulated fleets, not read off a normal table.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# channel key -> expected sign of the standardised deviation when the fault develops
SIGNATURES = {
    "SUCTION_STRAINER_CLOGGING": {"ps": -1, "n": +1, "pw": +1, "q": -1},
    "DISCHARGE_RESTRICTION": {"pd": +1, "q": -1, "i": -1, "pw": -1},
    "IMPELLER_WEAR": {"pd": -1, "i": -1, "q": -1, "pw": -1},
    "AIR_ENTRAINMENT": {"pd": -1, "q": -1, "pw": -1},
    "BEARING_WEAR": {"a": +1, "c": +1, "bt": +1, "v": +1},
    "MISALIGNMENT": {"v": +1, "bt": +1, "wt": +1, "pw": +1},
}
CLIP = 6.0
MIN_CHANNELS = 3          # after trimming the largest, at least two remain


def signature_scores(g: pd.DataFrame, smooth: int = 15, exclude: tuple = ()) -> pd.DataFrame:
    """Trimmed fused score per fault type for one asset, one value per minute (0 where fewer than MIN_CHANNELS channels report).

    Only steady running minutes count. `smooth` is the length in minutes of the causal rolling mean applied to each channel first."""
    steady = (g["steady"].to_numpy().astype(bool) & ~g["gap"].to_numpy().astype(bool))
    cache = {}
    out = {}
    for ft, sig in SIGNATURES.items():
        cols = []
        for k, s in sig.items():
            if f"z_{k}" not in g or k in exclude:
                continue
            if k not in cache:
                z = pd.Series(np.clip(g[f"z_{k}"].to_numpy(dtype=float), -CLIP, CLIP)).where(steady)
                if smooth > 1:                                    # sum over the window divided by sqrt(number of samples): unit variance for white noise at any fill
                    r = z.rolling(smooth, min_periods=max(1, smooth // 3))
                    cache[k] = (r.sum() / np.sqrt(r.count())).to_numpy()
                else:
                    cache[k] = z.to_numpy()
            cols.append(cache[k] * s)
        if len(cols) < MIN_CHANNELS:
            continue
        Z = np.column_stack(cols)
        present = ~np.isnan(Z)
        n = present.sum(axis=1)
        zz = np.where(present, Z, 0.0)
        top = np.where(present, Z, -np.inf).max(axis=1)
        rest = zz.sum(axis=1) - np.where(n > 0, top, 0.0)
        score = np.where(n >= MIN_CHANNELS, rest / np.sqrt(np.maximum(n - 1, 1)), 0.0)
        out[ft] = np.where(steady, score, 0.0)
    return pd.DataFrame(out, index=g.index)


def fused_flag(g: pd.DataFrame, h: float, smooth: int = 15, exclude: tuple = ()) -> np.ndarray:
    """Minutes where some fault's trimmed fused score is at least `h`."""
    sc = signature_scores(g, smooth, exclude)
    if sc.empty:
        return np.zeros(len(g), dtype=bool)
    return (sc.to_numpy() >= h).any(axis=1)


def fused_type(g: pd.DataFrame, smooth: int = 15, exclude: tuple = ()) -> pd.Series:
    """The fault type whose fused score is highest at each minute (None where all scores are zero)."""
    sc = signature_scores(g, smooth, exclude)
    if sc.empty:
        return pd.Series([None] * len(g), index=g.index, dtype=object)
    best = sc.idxmax(axis=1)
    return best.where(sc.max(axis=1) > 0)


def slow_detect(g: pd.DataFrame, h: float, k: float = 0.5, exclude: tuple = ()) -> tuple[np.ndarray, np.ndarray]:
    """One-sided CUSUM on the hourly mean of each (unsmoothed) trimmed fused score.

    A signature is hot from the start of the hour after the one in which its statistic exceeded `h`, and stays hot until the statistic returns to zero.
    Hourly means cut the autocorrelation of minute data, and the decision for an hour uses only that hour and earlier ones, so the result is causal.
    Returns (flag per minute, name of the hottest signature per minute, None where nothing is hot)."""
    sc = signature_scores(g, smooth=1, exclude=exclude)
    n = len(g)
    ok = g["steady"].to_numpy().astype(bool) & ~g["gap"].to_numpy().astype(bool)
    if sc.empty:
        return np.zeros(n, dtype=bool), np.array([None] * n, dtype=object)
    hour = pd.to_datetime(g["window_start_utc"], utc=True).dt.floor("h")
    grid = pd.date_range(hour.iloc[0], hour.iloc[-1] + pd.Timedelta(hours=1), freq="h")
    steady_h = pd.Series(ok).groupby(hour.to_numpy()).mean().reindex(grid[:-1]).fillna(0).to_numpy()
    heat = np.zeros((n, len(sc.columns)))
    for c, ft in enumerate(sc):
        hourly = sc[ft].groupby(hour.to_numpy()).mean().reindex(grid[:-1]).to_numpy()
        stat, hot, state = 0.0, False, np.zeros(len(grid))                  # state[j]: statistic of the hot signature at the start of grid[j]
        for j, (v, st) in enumerate(zip(hourly, steady_h)):
            if not np.isnan(v) and st >= 0.5:
                stat = max(0.0, stat + v - k)
                if stat > h:
                    hot = True
                elif stat == 0.0:
                    hot = False
            state[j + 1] = stat if hot else 0.0
        heat[:, c] = pd.Series(state, index=grid).reindex(hour.to_numpy()).to_numpy()
    heat = np.where(ok[:, None], heat, 0.0)
    flag = heat.max(axis=1) > 0
    names = np.array(list(sc.columns), dtype=object)
    kind = np.where(flag, names[heat.argmax(axis=1)], None)
    return flag, kind


def slow_flag(g: pd.DataFrame, h: float, k: float = 0.5, exclude: tuple = ()) -> np.ndarray:
    return slow_detect(g, h, k, exclude)[0]
