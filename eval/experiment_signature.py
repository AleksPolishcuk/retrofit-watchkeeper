#!/usr/bin/env python3
"""Does fusing channels along fault signatures (and a slow CUSUM on the fused score) find events earlier without raising false alerts?

One compact model is trained on the bank training fleets, then the same model is run with different signature thresholds on tune, dev (9 pumps),
trap and the healthy_train fleets (42 pumps x 7 days, no faults: every alert there is false). Thresholds are chosen on tune and healthy_train only.

  .venv/bin/python eval/experiment_signature.py            # default grid
  .venv/bin/python eval/experiment_signature.py 5:- -:12   # sig_h:slow_h pairs, '-' switches that detector off
  .venv/bin/python eval/experiment_signature.py --learn --drop=tf --train-healthy -:-   # --learn: per-regime baseline learning; other model options: blank channels, add healthy_train as NONE examples (then 'healthy' is reported)
Never reads the hold fleets or the test pumps.
"""
import sys
import time
import warnings

import pandas as pd

warnings.filterwarnings("ignore")

from watchkeeper import methods as M  # noqa: E402
from watchkeeper.bank import combine, load_set, load_trap  # noqa: E402
from watchkeeper.evalkit import concat_predictions, load_dev, score_ids  # noqa: E402
from watchkeeper.stats import delay_summary  # noqa: E402

GRID = ["-:-", "5:-", "6:-", "-:8", "-:12", "-:16", "6:12", "6:16"]


def parse(s):
    a, b = s.split(":")
    return (None if a == "-" else float(a)), (None if b == "-" else float(b))


def main() -> int:
    args = sys.argv[1:]
    drop = tuple(x.split("=")[1].split(",") for x in args if x.startswith("--drop="))[0] if any(x.startswith("--drop=") for x in args) else ()
    train_healthy = "--train-healthy" in args
    learn = "--learn" in args
    ctx = tuple(a.split("=")[1].split(",") for a in args if a.startswith("--ctx="))[0] if any(a.startswith("--ctx=") for a in args) else ()
    grid = [x for x in args if not x.startswith("--")] or GRID
    t0 = time.time()
    train = combine(load_set("train"), *([load_set("healthy_train")] if train_healthy else []))
    model = M.WKMethod(trees=60, min_leaf=25, max_depth=14, drop=drop, learn=learn, ctx=ctx).fit(train, train.ids)
    # the healthy set that is reported must not be the one that was trained on
    sets = {"tune": load_set("tune"), "dev9": load_dev(), "trap": load_trap(), ("healthy" if train_healthy else "healthy_train"): load_set("healthy" if train_healthy else "healthy_train")}
    print(f"trained [{time.time() - t0:.0f}s]", flush=True)
    rows = []
    for g in grid:
        sig_h, slow_h = parse(g)
        wk = M.WKMethod(trees=60, min_leaf=25, max_depth=14, sig_h=sig_h, slow_h=slow_h, drop=drop, learn=learn, ctx=ctx)
        for sname, d in sets.items():
            pred = concat_predictions(wk.predict(model, d, a) for a in d.ids)
            r = score_ids(pred, d, d.ids)
            by_rule = pred["rule"].value_counts().to_dict() if len(pred) else {}
            if sname.startswith("healthy"):
                days = r["asset_days"]
                rows.append({"cfg": g, "set": sname, "alerts": len(pred), "per pump-month": round(30 * len(pred) / days, 2), "episodes/pump-month": round(30 * r["false_alert_episodes"] / days, 2),
                             "by rule": by_rule})
                continue
            ds = delay_summary(r["per_event"])
            rows.append({"cfg": g, "set": sname, "composite": round(r["composite_score"], 1), "recall": round(r["event_recall"], 2), "type": round(r["fault_type_recall"], 2),
                         "FA/day": round(r["false_alerts_per_asset_day"], 2), "median delay h": None if ds.get("median_delay_h") is None else round(ds["median_delay_h"], 1),
                         "<=6h": f"{ds.get('within_6h', 0)}/{ds.get('events', 0)}", "before limit": f"{ds.get('before_deadline', 0)}/{ds.get('with_deadline', 0)}",
                         "sig alerts": by_rule.get("signature_sig", 0), "slow alerts": by_rule.get("signature_slow", 0)})
        df = pd.DataFrame(rows[-len(sets):])
        print(df.to_string(index=False, header=len(rows) == len(sets)), f"[{time.time() - t0:.0f}s]", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
