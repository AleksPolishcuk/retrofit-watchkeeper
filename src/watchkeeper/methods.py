"""Detection methods plugged into the evaluation kit. Add new methods to METHODS."""
from __future__ import annotations

import pandas as pd
from retrofit_sim import baselines as B

from .evalkit import DevData, Method, concat_predictions, score_ids
from .features.causal import causal_zscores


def _regime(data: DevData) -> pd.DataFrame:
    if "regime" not in data.cache:
        data.cache["regime"] = B.regime_frame(data.feat, data.assets)
    return data.cache["regime"]


def _zf(data: DevData, causal: bool = False) -> pd.DataFrame:
    """Regime frame with robust z-scores for the dev assets (each asset uses only its own data).

    causal=False is the organizer's baseline (first 24 h of the window). causal=True uses an expanding baseline.
    """
    key = "zf_causal" if causal else "zf"
    if key not in data.cache:
        data.cache[key] = causal_zscores(_regime(data)) if causal else B.zscores(_regime(data))
    return data.cache[key]


class B1Method(Method):
    """Organizer baseline B1 (mode-aware robust z). k and persistence are tuned on the fit assets only.

    Note: B1 takes its commissioning baseline from the first 24 h of the asset window, so an alert raised earlier than
    24 h uses statistics computed from later data. It is therefore not strictly causal.
    """

    name = "B1_mode_aware_z"
    CAUSAL = False
    GRID = [(k, m) for k in (4, 6, 8, 12) for m in (5, 15, 30)]

    def __init__(self, grid=None, fixed=None):
        self.grid = grid or self.GRID
        self.fixed = fixed

    def predict(self, params, data, asset_id):
        key = ("b1", self.CAUSAL, tuple(params), asset_id)
        if key not in data.cache:
            zf = _zf(data, self.CAUSAL)
            data.cache[key] = B.b1_threshold(zf[zf.asset_id == asset_id], *params)
        return data.cache[key]

    def fit(self, data, train_ids):
        if self.fixed:
            return self.fixed
        best, best_score = None, -1.0
        for p in self.grid:
            pred = concat_predictions(self.predict(p, data, a) for a in train_ids)
            s = score_ids(pred, data, train_ids)["composite_score"]
            if s > best_score:
                best, best_score = p, s
        return best


class B1CausalMethod(B1Method):
    """B1 with an expanding baseline, so that every alert depends only on data up to its own time."""

    name = "B1_causal"
    CAUSAL = True


METHODS = {
    "b1": B1Method,
    "b1c": B1CausalMethod,
}
