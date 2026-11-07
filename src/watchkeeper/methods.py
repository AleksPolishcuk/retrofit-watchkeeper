"""Detection methods plugged into the evaluation kit. Add new methods to METHODS."""
from __future__ import annotations

import numpy as np
import pandas as pd
from retrofit_sim import baselines as B

from .evalkit import INTERNAL_COLS, DevData, Method, concat_predictions, score_ids
from .detect.alerting import alerts_from_flag, b1_flag
from .detect.cavitation import cavitation_episodes
from .diagnose import ACTIONS, DiagnosisModel, event_class_of
from .features.causal import CH, build_features, causal_zscores, hold_sparse
from .features.npsh import npsh_margin


def _regime(data: DevData, hold: int = 0) -> pd.DataFrame:
    key = ("regime", hold)
    if key not in data.cache:
        f = B.regime_frame(data.feat, data.assets)
        data.cache[key] = hold_sparse(f, data.assets, hold) if hold else f
    return data.cache[key]


def _zf(data: DevData, causal: bool = False, thermal: int = 0, hold: int = 0) -> pd.DataFrame:
    """Regime frame with robust z-scores for the assets in `data` (each asset uses only its own data).

    causal=False is the organizer's baseline (first 24 h of the window). causal=True uses an expanding baseline. `thermal` blanks thermal
    channels for that many minutes after a restart; `hold` carries sparse wireless reports forward for that many minutes.
    """
    key = ("zf", causal, thermal, hold)
    if key not in data.cache:
        data.cache[key] = causal_zscores(_regime(data, hold), thermal_min=thermal) if causal else B.zscores(_regime(data, hold))
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


def _features(data: DevData, thermal: int = 0, hold: int = 0) -> pd.DataFrame:
    key = ("X", thermal, hold)
    if key not in data.cache:
        data.cache[key] = build_features(_zf(data, True, thermal, hold), data.assets)
    return data.cache[key]


# Process instruments on which an isolated deviation can be an instrument fault. Vibration channels come from one wireless sensor and
# winding temperature is slow and mostly a machine effect, so a lone deviation there is treated as machine, not instrument. The public
# fleet scenarios also place instrument faults on pressures, flow, motor current and bearing temperature only.
ARBITER_KEYS = ("ps", "pd", "q", "i", "pw", "bt")
STUCK_KEYS = ("pd", "ps", "q", "bt", "i", "tf")      # channels where a frozen value while running is a sensor fault


def _flag(row: pd.Series, key: str) -> bool:
    v = row.get(key, False)
    return bool(v) and not pd.isna(v)


def _rule_diagnosis(row: pd.Series, xrow: pd.Series | None = None, kz: float = 6.0, arbiter: bool = False) -> dict | None:
    """Deterministic instrument faults: a gateway gap, a channel frozen while the pump runs steadily, and (arbiter) one channel
    that deviates while every physically coupled channel stays quiet."""
    if _flag(row, "gap"):
        return {"event_class": "SENSOR", "fault_type": "COMMUNICATION_LOSS", "confidence": 0.9, "evidence": "missing rows",
                "action": ACTIONS["COMMUNICATION_LOSS"], "rule": "rule_gap"}
    if _flag(row, "steady"):
        for k in STUCK_KEYS:
            if _flag(row, "flat_" + k):
                return {"event_class": "SENSOR", "fault_type": "SENSOR_STUCK", "confidence": 0.85, "evidence": f"{CH[k]} frozen",
                        "action": ACTIONS["SENSOR_STUCK"], "rule": "rule_stuck"}
    if arbiter and xrow is not None:
        zv = {c: row.get("z_" + c) for c in CH}
        zv = {c: float(v) for c, v in zv.items() if v is not None and not pd.isna(v)}
        for c in sorted((c for c in zv if abs(zv[c]) > kz and c in ARBITER_KEYS), key=lambda c: -abs(zv[c])):
            cpl = [zv[x] for x in B.COUPLED[c] if x in zv]
            if cpl and max(abs(v) for v in cpl) < kz / 3:
                zs = row.get("zs_" + c)
                if zs is not None and not pd.isna(zs) and zs > kz:
                    ft = "SENSOR_NOISE_SPIKES"
                else:
                    step = abs(float(xrow.get("d30_" + c, 0.0))) > 0.6 * abs(zv[c])        # a jump within 30 min is an offset, a ramp is drift
                    ft = "SENSOR_CALIBRATION_SHIFT" if step else "SENSOR_DRIFT"
                return {"event_class": "SENSOR", "fault_type": ft, "confidence": 0.6, "evidence": f"{CH[c]} deviates alone (z={zv[c]:+.1f})",
                        "action": ACTIONS[ft], "rule": "rule_arbiter"}
    return None


def _evidence(row: pd.Series) -> str:
    """Top deviating channels in the text format that the export parses."""
    if bool(row.get("gap", False)):
        return "missing rows"
    zs = [(CH[k], row.get("z_" + k)) for k in CH]
    zs = sorted([(c, float(v)) for c, v in zs if pd.notna(v) and abs(v) >= 2.0], key=lambda cv: -abs(cv[1]))[:3]
    frozen = [CH[k] for k in CH if _flag(row, "flat_" + k)]
    parts = [f"{c} z={v:+.1f}" for c, v in zs] + [f"{c} frozen" for c in frozen[:1]]
    return ", ".join(parts) if parts else "no single channel stands out"


class WKMethod(Method):
    """Causal baseline, B1 trigger, learned diagnosis. `fit` trains the classifier on the given pumps only."""

    name = "WK_causal_learned"           # with deterministic rules for gaps and frozen channels (rules=True)

    def __init__(self, k=6.0, persist=15, suppress=0.6, none_weight=0.5, k_low=4.0, trees=100, rules=True, cavitation=True, arbiter=True, thermal=60, hold=6):
        self.k, self.persist, self.suppress, self.none_weight, self.k_low, self.trees = k, persist, suppress, none_weight, k_low, trees
        self.rules, self.cavitation, self.arbiter = rules, cavitation, arbiter
        self.thermal, self.hold = thermal, hold

    def fit(self, data, train_ids):
        return DiagnosisModel(self.k_low, self.none_weight, self.trees).fit(_zf(data, True, self.thermal, self.hold), _features(data, self.thermal, self.hold), data.events, train_ids)

    def predict(self, model, data, asset_id):
        key = ("wk", id(model), asset_id, self.k, self.persist, self.suppress, self.rules, self.cavitation, self.arbiter, self.thermal, self.hold)
        if key in data.cache:
            return data.cache[key]
        zf, X = _zf(data, True, self.thermal, self.hold), _features(data, self.thermal, self.hold)
        idx = zf.index[zf.asset_id == asset_id]
        g, Xa = zf.loc[idx].reset_index(drop=True), X.loc[idx]
        P = model.proba(Xa)
        cav_rows, cav_active = [], np.zeros(len(g), dtype=bool)
        if self.cavitation:
            cav_rows, cav_active = cavitation_episodes(g, npsh_margin(g, data.assets.set_index("asset_id").loc[asset_id]).to_numpy())
            for r in cav_rows:
                r["recommended_action"] = ACTIONS["CAVITATION"]
                r["rule"], r["alternatives"] = "cavitation", "[]"
        classes = model.classes_
        none_i = classes.index("NONE") if "NONE" in classes else None
        type_i = [i for i, c in enumerate(classes) if c != "NONE"]

        def diag(j):
            if self.rules:
                r = _rule_diagnosis(g.iloc[j], Xa.iloc[j], self.k, self.arbiter)
                if r is not None:
                    return r
            if cav_active[j]:
                return None                      # a confirmed cavitation episode explains the symptoms; do not add a second diagnosis
            p = P[j]
            pn = float(p[none_i]) if none_i is not None else 0.0
            if pn >= self.suppress:
                return None
            pt = p[type_i]
            ft = classes[type_i[int(pt.argmax())]] if pt.sum() > 0 else "UNKNOWN"
            conf = float(pt.max() / pt.sum() * (1 - pn)) if pt.sum() > 0 else 0.3
            order = np.argsort(-pt)[1:4] if pt.sum() > 0 else []
            alts = [{"fault_type": classes[type_i[int(i)]], "p": round(float(pt[i] / pt.sum()), 3)} for i in order if pt[i] / pt.sum() >= 0.05]
            return {"event_class": event_class_of(ft), "fault_type": ft, "confidence": min(max(conf, 0.05), 0.99),
                    "evidence": _evidence(g.iloc[j]), "action": ACTIONS[ft], "alternatives": alts, "rule": "model"}

        rows = alerts_from_flag(g, b1_flag(g, self.k), self.persist, diag, "WK causal+learned")
        rows += [dict(r, evidence="WK causal+learned: " + r["evidence"]) for r in cav_rows]
        out = pd.DataFrame(sorted(rows, key=lambda r: r["alert_time_utc"]), columns=INTERNAL_COLS)
        data.cache[key] = out
        return out


METHODS = {
    "b1": B1Method,
    "b1c": B1CausalMethod,
    "wk": WKMethod,
    "wk-learned-only": lambda: WKMethod(rules=False),
    "wk-no-arbiter": lambda: WKMethod(arbiter=False),
}
