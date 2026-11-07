#!/usr/bin/env python3
"""Train a compact model per variant on the bank training fleets and compare on tune, dev and trap, including how early events are found.

  .venv/bin/python eval/experiment_variants.py base no_tf no_thermal
Never reads the hold fleets or the test pumps.
"""
import sys
import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from watchkeeper import methods as M  # noqa: E402
from watchkeeper.bank import combine, load_set, load_trap  # noqa: E402
from watchkeeper.evalkit import concat_predictions, load_dev, score_ids  # noqa: E402
from watchkeeper.features.causal import build_features  # noqa: E402
from watchkeeper.stats import delay_summary  # noqa: E402

THERMAL, KEYS = ("wt", "bt", "tf"), None
VARIANTS = {"base": (), "no_tf": ("tf",), "no_thermal": THERMAL}


def apply_drop(data, drop):
    """Blank the given channels in the cached causal z-scores and rebuild the features from them (same cache keys the method reads)."""
    zf = M._zf(data, True, 60, 6).copy()
    for k in drop:
        for pre in ("z_", "zs_", "flat_"):
            if pre + k in zf:
                zf[pre + k] = np.nan if pre != "flat_" else False
    data.cache[("zf", True, 60, 6)] = zf
    data.cache[("X", 60, 6)] = build_features(zf, data.assets)
    return data


def main() -> int:
    names = sys.argv[1:] or list(VARIANTS)
    rows, t0 = [], time.time()
    for name in names:
        drop = VARIANTS[name]
        train = apply_drop(combine(load_set("train")), drop)
        wk = M.WKMethod(trees=60, min_leaf=25, max_depth=14)
        model = wk.fit(train, train.ids)
        for sname, d in (("tune", load_set("tune")), ("dev9", load_dev()), ("trap", load_trap())):
            d = apply_drop(d, drop)
            pred = concat_predictions(wk.predict(model, d, a) for a in d.ids)
            r = score_ids(pred, d, d.ids)
            ds = delay_summary(r["per_event"])
            rows.append({"variant": name, "set": sname, "composite": round(r["composite_score"], 1), "recall": round(r["event_recall"], 2), "type": round(r["fault_type_recall"], 2),
                         "FA/day": round(r["false_alerts_per_asset_day"], 2), "median delay h": None if ds.get("median_delay_h") is None else round(ds["median_delay_h"], 1),
                         "<=6h": f"{ds.get('within_6h', 0)}/{ds.get('events', 0)}", "before limit": f"{ds.get('before_deadline', 0)}/{ds.get('with_deadline', 0)}"})
        print(pd.DataFrame(rows[-3:]).to_string(index=False, header=len(rows) == 3), f"[{time.time() - t0:.0f}s]", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
