"""Detection methods plugged into the evaluation kit. Add new methods to METHODS."""
from __future__ import annotations

import numpy as np
import pandas as pd
from retrofit_sim import baselines as B

from .evalkit import INTERNAL_COLS, DevData, Method, concat_predictions, score_ids
from .detect.alerting import alerts_from_flag, alerts_from_flags, b1_flag, split_flags
from .detect.cavitation import cavitation_episodes
from .detect.signature import SIGNATURES, fused_flag, fused_type, slow_detect
from .diagnose import ACTIONS, DiagnosisModel, event_class_of
from .features.causal import CH, build_features, causal_zscores, hold_sparse
from .features.hygiene import clean_minutes
from .features.npsh import npsh_margin


ROBUST = ("flatstrict", "longdev", "speedloss")       # longdev8 and longdev12 are the same rule with 8 and 12 hours of persistence
OPTIONS_DOC = None       # data-quality options: stricter frozen-sensor rule, persistent unexplained deviation, speed-signal loss. Off by default (the submitted model is freeze-v1).


def _suspend_on_speed_loss(f: pd.DataFrame, assets: pd.DataFrame, hold_min: int = 15) -> pd.DataFrame:
    """A drive that had a speed signal and loses it while running: after `hold_min` minutes no minute counts as steady until the signal returns.
    Without this the missing speed makes a new operating regime and the pump is judged against a baseline learned from whatever followed (scenario A04)."""
    has_speed = {r.asset_id: "motor_speed_rpm" in str(r.channels_available).split("|") for r in assets.itertuples()}
    f = f.copy()
    for a, idx in f.groupby("asset_id").groups.items():
        if not has_speed.get(a) or "speed_ratio" not in f:
            continue
        lost = ((f.loc[idx, "operating_mode"] == "RUNNING") & f.loc[idx, "speed_ratio"].isna()).to_numpy()
        run, flag = 0, np.zeros(len(lost), dtype=bool)
        for j, v in enumerate(lost):
            run = run + 1 if v else 0
            flag[j] = run > hold_min
        if flag.any():
            f.loc[idx[flag], "steady"] = False
    return f


def _regime(data: DevData, hold: int = 0, ctx: tuple = ()) -> pd.DataFrame:
    """Regime frame. Repeated minutes are removed first (scenario A14). With "demand" in `ctx`, the regime key also contains the cooling demand from the operating
    context (15 percent bins); with "speedloss", minutes after the speed signal was lost are not steady. `ctx` is a tuple of option names."""
    ctx = tuple(sorted(ctx))
    key = ("regime", hold) + ((ctx,) if ctx else ())
    if key not in data.cache:
        feat, report = clean_minutes(data.feat)
        data.cache[("hygiene", "report")] = report
        f = B.regime_frame(feat, data.assets)
        if "speedloss" in ctx:
            f = _suspend_on_speed_loss(f, data.assets)
        if "demand" in ctx and "ctx_duty_demand_pct" in f:
            d = f["ctx_duty_demand_pct"].to_numpy(dtype=float)
            f["regime"] = f["regime"].astype(int) * 100 + np.where(np.isnan(d), 0, np.clip(np.round(d / 15.0), 0, 9)).astype(int)
        data.cache[key] = hold_sparse(f, data.assets, hold) if hold else f
    return data.cache[key]


def _zf(data: DevData, causal: bool = False, thermal: int = 0, hold: int = 0, drop: tuple = (), learn: bool = False, ctx: tuple = ()) -> pd.DataFrame:
    """Regime frame with robust z-scores for the assets in `data` (each asset uses only its own data).

    causal=False is the organizer's baseline (first 24 h of the window). causal=True uses an expanding baseline. `thermal` blanks thermal
    channels for that many minutes after a restart; `hold` carries sparse wireless reports forward for that many minutes.
    `drop` names channel keys (such as "tf") that are blanked: they take no part in triggering, features or evidence.
    """
    drop = tuple(sorted(drop))
    ctx = tuple(sorted(ctx))
    key = ("zf", causal, thermal, hold) + ((drop,) if drop else ()) + (("learn",) if learn else ()) + ((ctx,) if ctx else ())
    if key not in data.cache:
        if drop:
            zf = _zf(data, causal, thermal, hold, (), learn, ctx).copy()
            for k in drop:
                for pre in ("z_", "zs_"):
                    if pre + k in zf:
                        zf[pre + k] = np.nan
                if "flat_" + k in zf:
                    zf["flat_" + k] = False
            data.cache[key] = zf
        else:
            data.cache[key] = causal_zscores(_regime(data, hold, ctx), thermal_min=thermal, learn=learn, tf_adj="tfadj" in ctx, flat_strict="flatstrict" in ctx) if causal else B.zscores(_regime(data, hold))
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


def _features(data: DevData, thermal: int = 0, hold: int = 0, drop: tuple = (), learn: bool = False, ctx: tuple = ()) -> pd.DataFrame:
    drop = tuple(sorted(drop))
    ctx = tuple(sorted(ctx))
    key = ("X", thermal, hold) + ((drop,) if drop else ()) + (("learn",) if learn else ()) + ((ctx,) if ctx else ())
    if key not in data.cache:
        data.cache[key] = build_features(_zf(data, True, thermal, hold, drop, learn, ctx), data.assets, ctx_feat="feat" in ctx)
    return data.cache[key]


# Process instruments on which an isolated deviation can be an instrument fault. Vibration channels come from one wireless sensor and
# winding temperature is slow and mostly a machine effect, so a lone deviation there is treated as machine, not instrument. The public
# fleet scenarios also place instrument faults on pressures, flow, motor current and bearing temperature only.
ARBITER_KEYS = ("ps", "pd", "q", "i", "pw", "bt")
STUCK_KEYS = ("pd", "ps", "q", "bt", "i", "tf")      # channels where a frozen value while running is a sensor fault


def _flag(row: pd.Series, key: str) -> bool:
    v = row.get(key, False)
    return bool(v) and not pd.isna(v)


def _rule_diagnosis(row: pd.Series, xrow: pd.Series | None = None, kz: float = 6.0, arbiter: bool = False, only: str | None = None) -> dict | None:
    """Deterministic instrument faults: a gateway gap, a channel frozen while the pump runs steadily, and (arbiter) one channel
    that deviates while every physically coupled channel stays quiet."""
    if only in (None, "gap") and _flag(row, "gap"):
        return {"event_class": "SENSOR", "fault_type": "COMMUNICATION_LOSS", "confidence": 0.9, "evidence": "missing rows",
                "action": ACTIONS["COMMUNICATION_LOSS"], "rule": "rule_gap"}
    if only in (None, "stuck") and _flag(row, "steady"):
        for k in STUCK_KEYS:
            if _flag(row, "flat_" + k):
                return {"event_class": "SENSOR", "fault_type": "SENSOR_STUCK", "confidence": 0.85, "evidence": f"{CH[k]} frozen",
                        "action": ACTIONS["SENSOR_STUCK"], "rule": "rule_stuck"}
    if only in (None, "dev") and arbiter and xrow is not None:
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


def _signature_evidence(xrow: pd.Series, ft: str, how: str) -> str:
    """Evidence for an alert raised from fused weak shifts: the channels of the fault's signature with their 15-minute mean deviation, signed by the
    direction the fault is expected to push them, in the same text format as `_evidence`."""
    parts = []
    for k, sign in SIGNATURES[ft].items():
        v = xrow.get("m15_" + k)
        if v is not None and pd.notna(v) and abs(v) >= 0.5 and np.sign(v) == sign:
            parts.append((abs(float(v)), f"{CH[k]} z={float(v):+.1f}"))
    parts = [t for _, t in sorted(parts, reverse=True)[:4]]
    return ", ".join(parts + [f"{how} matches the {ft} signature"])


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

    def __init__(self, k=5.0, persist=12, suppress=0.6, none_weight=0.5, k_low=4.0, trees=100, rules=True, cavitation=True, arbiter=True, thermal=60, hold=6, min_leaf=3, max_depth=None,
                 sig_h=None, slow_h=None, slow_k=0.5, sig_smooth=15, sig_persist=12, drop=(), learn=True, ctx=()):
        self.k, self.persist, self.suppress, self.none_weight, self.k_low, self.trees = k, persist, suppress, none_weight, k_low, trees
        self.rules, self.cavitation, self.arbiter = rules, cavitation, arbiter
        self.thermal, self.hold = thermal, hold
        self.min_leaf, self.max_depth = min_leaf, max_depth
        self.sig_h, self.slow_h, self.slow_k, self.sig_smooth, self.sig_persist = sig_h, slow_h, slow_k, sig_smooth, sig_persist
        self.drop = tuple(sorted(drop))
        self.learn = learn
        self.ctx = tuple(sorted(ctx))

    def fit(self, data, train_ids):
        return DiagnosisModel(self.k_low, self.none_weight, self.trees, min_leaf=self.min_leaf, max_depth=self.max_depth).fit(_zf(data, True, self.thermal, self.hold, self.drop, self.learn, self.ctx), _features(data, self.thermal, self.hold, self.drop, self.learn, self.ctx), data.events, train_ids)

    def predict(self, model, data, asset_id):
        key = ("wk", id(model), asset_id, self.k, self.persist, self.suppress, self.rules, self.cavitation, self.arbiter, self.thermal, self.hold,
               self.sig_h, self.slow_h, self.slow_k, self.sig_smooth, self.sig_persist, self.drop, self.learn, self.ctx)
        if key in data.cache:
            return data.cache[key]
        zf, X = _zf(data, True, self.thermal, self.hold, self.drop, self.learn, self.ctx), _features(data, self.thermal, self.hold, self.drop, self.learn, self.ctx)
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

        flags = split_flags(g, self.k)
        persist = {"dev": self.persist, "gap": min(self.persist, 8), "stuck": self.persist}
        kinds = {}
        long_min = 720 if "longdev12" in self.ctx else 480 if "longdev8" in self.ctx else 360 if "longdev" in self.ctx else 0
        if long_min:
            flags["long"], persist["long"] = flags["dev"].copy(), long_min
        if self.sig_h is not None:
            flags["sig"], persist["sig"] = fused_flag(g, self.sig_h, self.sig_smooth), self.sig_persist
            kinds["sig"] = fused_type(g, self.sig_smooth).to_numpy()
        if self.slow_h is not None:
            flags["slow"], kinds["slow"] = slow_detect(g, self.slow_h, self.slow_k)
            persist["slow"] = 1                                   # the hourly decision is already persistent

        def diag(j, reason):
            if reason in ("sig", "slow"):
                ft = kinds[reason][j]
                if ft is None or cav_active[j]:
                    return None
                how = "fused weak shifts" if reason == "sig" else "slow cumulative change"
                return {"event_class": event_class_of(ft), "fault_type": ft, "confidence": 0.5 if reason == "sig" else 0.4,
                        "evidence": _signature_evidence(Xa.iloc[j], ft, how), "action": ACTIONS[ft], "alternatives": [], "rule": "signature_" + reason}
            if reason == "long":
                # six hours of departure from the pump's own normal that the model keeps explaining away as normal: say so instead of staying silent
                if cav_active[j]:
                    return None
                if self.rules and _rule_diagnosis(g.iloc[j], Xa.iloc[j], self.k, self.arbiter, only="dev") is not None:
                    return None
                pn = float(P[j][none_i]) if none_i is not None else 0.0
                if pn < self.suppress:
                    return None                  # the model path alerts by itself
                return {"event_class": event_class_of("UNKNOWN"), "fault_type": "UNKNOWN", "confidence": 0.4, "alternatives": [], "rule": "persistent_unexplained",
                        "evidence": f"persistent departure from this pump's own normal for {persist['long'] // 60} hours, cause not identified: " + _evidence(g.iloc[j]), "action": ACTIONS["UNKNOWN"]}
            if reason in ("gap", "stuck"):
                if self.rules:
                    return _rule_diagnosis(g.iloc[j], Xa.iloc[j], self.k, False, only=reason)
                return None
            if self.rules:
                r = _rule_diagnosis(g.iloc[j], Xa.iloc[j], self.k, self.arbiter, only="dev")
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

        rows = alerts_from_flags(g, flags, persist, diag, "WK causal+learned")
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
    "wk-sig": lambda: WKMethod(sig_h=5.0, slow_h=8.0),
    "wk-no-tf": lambda: WKMethod(drop=("tf",)),
    "wk-no-learn": lambda: WKMethod(learn=False),
}
