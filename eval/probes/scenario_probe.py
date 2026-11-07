#!/usr/bin/env python3
"""How does our pipeline behave in the enterprise verification scenarios? Real minute features of a healthy simulated pump are perturbed the way each scenario
describes, then run through the frozen model (models/wk.joblib). Reports alerts, crashes and what a user would be told. Healthy bank fleets only; no public or test pump.

  .venv/bin/python eval/probes/scenario_probe.py        # writes eval/results/scenarios_probe.md
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from watchkeeper.bank import load_set  # noqa: E402
from watchkeeper.diagnose import DiagnosisModel  # noqa: E402
from watchkeeper.evalkit import ROOT, DevData  # noqa: E402
from watchkeeper.methods import WKMethod  # noqa: E402

MODEL = DiagnosisModel.load(ROOT / "models" / "wk.joblib")


def run(feat: pd.DataFrame, assets: pd.DataFrame, asset: str):
    d = DevData(Path("."), assets, feat.copy(), pd.DataFrame(columns=["asset_id"]), pd.DataFrame(), pd.DataFrame())
    try:
        return WKMethod().predict(MODEL, d, asset), None
    except Exception as e:                                           # a crash is a result, not a script error
        return None, f"{type(e).__name__}: {str(e)[:70]}"


def summarize(pred, err):
    if err:
        return f"CRASH {err}"
    if pred is None or len(pred) == 0:
        return "no alert"
    t = pd.to_datetime(pred.alert_time_utc, utc=True)
    return f"{len(pred)} alert(s): " + "; ".join(f"{r.fault_type} {t.iloc[i].strftime('%d %b %H:%M')}" for i, r in enumerate(pred.itertuples()))[:150]


def longest_running(feat: pd.DataFrame, after_h: float = 30, min_h: float = 3):
    """Start index and length (minutes) of the longest continuous RUNNING stretch after `after_h` hours."""
    run = (feat["operating_mode"] == "RUNNING").to_numpy()
    best, start, n = (0, 0), None, 0
    for j in range(int(after_h * 60), len(run)):
        if run[j]:
            start = j if start is None else start
            n = j - start + 1
            if n > best[1]:
                best = (start, n)
        else:
            start = None
    return best


def main() -> int:
    d = load_set("healthy")
    assets = d.assets
    # pick the quiet healthy pumps: one fully instrumented, one retrofit
    quiet = {}
    for a in d.ids:
        f = d.feat[d.feat.asset_id == a].reset_index(drop=True)
        pred, err = run(f, assets, a)
        tier = assets.set_index("asset_id").loc[a, "instrumentation_tier"]
        if err is None and len(pred) == 0 and tier not in quiet and best_ok(f):
            quiet[tier] = a
        if "T2_FULL" in quiet and "T1_RETROFIT" in quiet:
            break
    rows = []
    t2, t1 = quiet.get("T2_FULL"), quiet.get("T1_RETROFIT")
    base2 = d.feat[d.feat.asset_id == t2].reset_index(drop=True)
    s0, n0 = longest_running(base2)
    ix = s0 + 60                                                       # one hour into the longest running stretch
    print(f"T2 pump {t2}, injection start index {ix}, running stretch {n0} min; T1 pump {t1}", flush=True)

    def dev(f, a, b, q=0.8, pd_=1.12, i=0.9):
        f = f.copy()
        sl = slice(a, b)
        for col, k in (("flow_m3_h__mean", q), ("discharge_pressure_kpa__mean", pd_), ("motor_current_a__mean", i)):
            if col in f:
                f.loc[f.index[sl], col] = f.loc[f.index[sl], col] * k
        return f

    def add(sid, name, feat, asset, note=""):
        pred, err = run(feat, assets, asset)
        rows.append((sid, name, summarize(pred, err), note))
        print(sid, rows[-1][2], flush=True)

    add("A01", "stable, correct data", base2, t2)
    f = base2.drop(base2.index[ix:ix + 4]).reset_index(drop=True)
    add("A02a", "gateway silent for 4 minutes", f, t2, "our gap rule needs 8 minutes")
    f = base2.drop(base2.index[ix:ix + 12]).reset_index(drop=True)
    add("A02b", "gateway silent for 12 minutes", f, t2)
    f = base2.copy()
    for c in [c for c in f.columns if c.startswith("suction_pressure_kpa__")]:
        f.loc[f.index[ix:], c] = np.nan if not c.endswith("__count") else 0
    add("A03", "suction pressure channel stops, gateway alive", f, t2, "no dynamic channel-loss notice")
    f = base2.copy()
    for c in [c for c in f.columns if c.startswith("motor_speed_rpm__")]:
        f.loc[f.index[ix:], c] = np.nan if not c.endswith("__count") else 0
    add("A04", "speed signal of the drive disappears", f, t2, "false alerts for days: the missing speed makes a new operating regime")
    add("A05", "flow and pressure deviation for 8 minutes", dev(base2, ix, ix + 8), t2)
    add("A06", "flow and pressure deviation for 20 minutes", dev(base2, ix, ix + 20), t2, "the trigger fires (z up to 31) but the classifier says NONE, 70 to 74 percent, so the alert is suppressed")
    f = dev(base2, ix, ix + 40)
    f.loc[f.index[ix:ix + 40], "quality_any"] = True
    add("A11", "same deviation, readings flagged OUT_OF_RANGE", f, t2, "quality flags are not used")
    f = base2.copy()
    sd = "discharge_pressure_kpa__std"
    f.loc[f.index[ix:ix + 40], sd] = 0.0
    f.loc[f.index[ix:ix + 40], "discharge_pressure_kpa__mean"] = f.loc[f.index[ix:ix + 40], "discharge_pressure_kpa__mean"].to_numpy() + np.linspace(0, 3, 40)
    add("A12", "pressure constant inside minutes, changing between minutes", f, t2, "stuck rule looks at spread inside a minute only")
    f = pd.concat([base2.iloc[:ix + 5], base2.iloc[ix + 4:ix + 5], base2.iloc[ix + 5:]]).reset_index(drop=True)
    add("A14", "a row with the same minute arrives twice", f, t2)
    f = dev(base2, ix, min(ix + 14 * 60, s0 + n0))
    add("A15", f"continuous deviation for {min(14 * 60, n0 - 60) // 60} hours", f, t2, "contract v2 groups the reminders into one incident")
    f = base2.copy()
    for c in [c for c in f.columns if c.endswith(("__mean", "__std", "__min", "__max", "__last"))]:
        f.loc[f.index[ix:ix + 120], c] = np.nan
    for c in [c for c in f.columns if c.endswith("__count")]:
        f.loc[f.index[ix:ix + 120], c] = 0
    add("A18", "rows arrive but every physical measurement is missing (2 h)", f, t2, "nothing tells the user that evaluation is impossible")
    if t1:
        base1 = d.feat[d.feat.asset_id == t1].reset_index(drop=True)
        s1, n1 = longest_running(base1)
        j = s1 + 60
        f = base1.copy()
        vib = [c for c in f.columns if c.startswith("vibration_rms_mm_s__mean")]
        have = f.loc[f.index[j:j + 140], "vibration_rms_mm_s__count"].fillna(0).to_numpy() > 0 if "vibration_rms_mm_s__count" in f else np.zeros(140, bool)
        for c in vib:
            idx = f.index[j:j + 140][have]
            f.loc[idx, c] = f.loc[idx, c] * 3.0
        add("A10", f"T1: {int(have.sum())} abnormal wireless vibration samples, 5 minutes apart", f, t1)
    out = ["# Scenario probe: how Watchkeeper behaves in the enterprise verification scenarios", "",
           "Real minute features of quiet healthy simulated pumps are perturbed as each scenario describes and run through the frozen model. No public or test pump is used.", "",
           "| Scenario | What was done | Result | Note |", "|---|---|---|---|"]
    out += [f"| {a} | {b} | {c} | {n} |" for a, b, c, n in rows]
    Path(ROOT / "eval" / "results" / "scenarios_probe.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    return 0


def best_ok(f):
    return longest_running(f)[1] >= 14 * 60 + 120


if __name__ == "__main__":
    sys.exit(main())
