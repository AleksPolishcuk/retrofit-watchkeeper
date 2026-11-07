#!/usr/bin/env python3
"""The one results table: dev pumps, tune fleets, trap, optionally the untouched hold fleets, and the healthy fleets for false alerts.

  .venv/bin/python eval/run_report.py --model models/wk.joblib            # hold fleets stay untouched
  .venv/bin/python eval/run_report.py --model models/wk.joblib --hold     # only when the method is frozen
Reads no test pump. Writes eval/results/final/report.md and report.json.
"""
import argparse
import json
import sys
import time
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

from watchkeeper import methods as M  # noqa: E402
from watchkeeper.bank import load_set, load_trap  # noqa: E402
from watchkeeper.diagnose import DiagnosisModel  # noqa: E402
from watchkeeper.evalkit import ROOT, concat_predictions, load_dev, score_ids  # noqa: E402
from watchkeeper.stats import bootstrap, per_asset, poisson_upper, random_alerts  # noqa: E402


def run(method, params, data, ids=None):
    return concat_predictions(method.predict(params, data, a) for a in (ids or data.ids))


def fmt(x, d=2):
    return "-" if x is None or (isinstance(x, float) and pd.isna(x)) else f"{x:.{d}f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(ROOT / "models" / "wk.joblib"))
    ap.add_argument("--hold", action="store_true", help="include the untouched hold fleets (use once, at freeze)")
    ap.add_argument("--k", type=float, default=None)
    ap.add_argument("--persist", type=int, default=None)
    ap.add_argument("--out", default=str(ROOT / "eval" / "results" / "final"))
    a = ap.parse_args()
    t0 = time.time()
    model = DiagnosisModel.load(a.model)
    kw = {k: v for k, v in (("k", a.k), ("persist", a.persist)) if v is not None}
    wk = M.WKMethod(**kw)
    sets = {"9 public dev pumps": load_dev(), "tune fleets (16 pumps)": load_set("tune"), "masked-clogging trap (3 pumps)": load_trap()}
    if a.hold:
        sets["hold fleets (24 pumps)"] = load_set("hold")
    rows, detail, jsonout = [], {}, {}
    for name, data in sets.items():
        preds = {"WK": run(wk, model, data), "B1 organizer": run(M.B1Method(fixed=(6, 15)), (6, 15), data), "B1 causal": run(M.B1CausalMethod(fixed=(6, 15)), (6, 15), data)}
        for mname, pred in preds.items():
            r = score_ids(pred, data, data.ids)
            st = per_asset(pred, data) if mname == "WK" or len(data.ids) > 3 else None
            lo, _, hi = bootstrap(st, reps=1000) if st and len(data.ids) > 3 else (float("nan"), 0, float("nan"))
            rows.append(dict(set=name, method=mname, composite=r["composite_score"], lo=lo, hi=hi, f1=r["event_f1"], recall=r["event_recall"], prec=r["alert_precision"],
                             fa=r["false_alerts_per_asset_day"], type=r["fault_type_recall"], cls=r["class_recall"], events=r["events_scored"]))
            if mname == "WK":
                pe = pd.DataFrame(r["per_event"])
                tier = dict(zip(data.assets.asset_id, data.assets.instrumentation_tier))
                pe["tier"] = pe.asset_id.map(tier)
                detail[name] = {"tier": pe.groupby("tier").agg(events=("event_id", "count"), detected=("detected", "sum"), right_type=("type_correct", "sum")),
                                "type": pe.groupby("fault_type").agg(events=("event_id", "count"), detected=("detected", "sum"), right_type=("type_correct", "sum")),
                                "null": random_alerts(pred, data, draws=10)}
        jsonout[name] = {"wk": next(r for r in rows if r["set"] == name and r["method"] == "WK"), "null_random_alerts": detail[name]["null"]}
        print(f"{name}: done [{time.time() - t0:.0f}s]", flush=True)
    hd = load_set("healthy")
    hp = run(wk, model, hd)
    hr = score_ids(hp, hd, hd.ids)
    n_false = hr["false_alert_episodes"] + hr["excess_repeat_episodes"]
    days = hr["asset_days"]
    healthy = dict(pump_days=days, alerts=int(len(hp)), false_episodes=int(n_false), per_pump_day=n_false / days, per_pump_month=30 * n_false / days,
                   upper95_per_pump_month=30 * poisson_upper(int(n_false), days))
    jsonout["healthy"] = healthy

    L = ["# Results", "", f"Model: `{Path(a.model).name}`. Composite is the organizers' scorer. Intervals resample pumps (1000 draws).", "",
         "| Set | Method | Composite (95% interval) | F1 | Recall | Precision | False + repeat per pump-day | Type recall | Class recall | Events |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        ci = f"{r['composite']:.1f} ({r['lo']:.0f} to {r['hi']:.0f})" if r["method"] == "WK" and r["lo"] == r["lo"] else f"{r['composite']:.1f}"
        L.append(f"| {r['set']} | {'**WK**' if r['method'] == 'WK' else r['method']} | {ci} | {fmt(r['f1'])} | {fmt(r['recall'])} | {fmt(r['prec'])} | {fmt(r['fa'])} | {fmt(r['type'])} | {fmt(r['cls'])} | {r['events']} |")
    L += ["", "Null detector (same number of alerts per pump, random times, same type mix): " + ", ".join(f"{k} {v['null']:.1f}" for k, v in detail.items()) +
          ". An alert-free detector scores 10.", "", "## Healthy fleets (no faults, every alert is false)", "",
          f"{days:.0f} pump-days, {healthy['alerts']} alerts, {n_false} false episodes. Rate **{healthy['per_pump_day']:.3f} per pump-day, {healthy['per_pump_month']:.2f} per pump-month** "
          f"(upper 95% bound {healthy['upper95_per_pump_month']:.2f}). Design budget: at most 1 per pump per quarter (0.33 per pump-month).", ""]
    for name, d in detail.items():
        L += [f"## {name}: by instrumentation tier", "", "| Tier | Events | Detected | Right type |", "|---|---|---|---|"]
        L += [f"| {i} | {int(r.events)} | {int(r.detected)} | {int(r.right_type)} |" for i, r in d["tier"].iterrows()]
        L += ["", f"## {name}: by fault type", "", "| Type | Events | Detected | Right type |", "|---|---|---|---|"]
        L += [f"| {i} | {int(r.events)} | {int(r.detected)} | {int(r.right_type)} |" for i, r in d["type"].iterrows()]
        L.append("")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (out / "report.json").write_text(json.dumps(jsonout, indent=2, default=float) + "\n", encoding="utf-8")
    print("\n".join(L[:3 + len(rows) + 6]))
    print(f"-> {out} ({time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
