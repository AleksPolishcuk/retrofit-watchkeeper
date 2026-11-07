#!/usr/bin/env python3
"""What happens when a sensor is missing or fails? Run the frozen model on the untouched hold fleets with whole channels removed from the data (not just from the
features), and compare with the full data. This is the retrofit question: how much does it matter if a plant only has some of the sensors?

  .venv/bin/python eval/probes/missing_sensor.py        # writes eval/results/missing_sensor.md
Reads only the bank hold fleets. Uses models/wk.joblib, which was not trained on them.
"""
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from retrofit_sim import baselines as B  # noqa: E402

from watchkeeper import methods as M  # noqa: E402
from watchkeeper.bank import load_set  # noqa: E402
from watchkeeper.diagnose import DiagnosisModel  # noqa: E402
from watchkeeper.evalkit import ROOT, concat_predictions, score_ids  # noqa: E402
from watchkeeper.stats import delay_summary  # noqa: E402

SCENARIOS = {
    "all channels": (),
    "no suction pressure": ("ps",),
    "no flow and no power": ("q", "pw"),
    "no vibration sensor": ("v", "a", "c"),
    "no bearing and winding temperature": ("bt", "wt"),
    "no discharge pressure": ("pd",),
}


def mask(data, keys):
    feat = data.feat.copy()
    for k in keys:
        col = B.CH[k]
        for c in [c for c in feat.columns if c.startswith(col + "__")]:
            feat[c] = 0 if c.endswith("__count") else np.nan
    return data.__class__(data.root, data.assets, feat, data.events, data.benign, data.alarms)


def main() -> int:
    model = DiagnosisModel.load(ROOT / "models" / "wk.joblib")
    hold = load_set("hold")
    rows, t0 = [], time.time()
    for name, keys in SCENARIOS.items():
        d = mask(hold, keys)
        pred = concat_predictions(M.WKMethod().predict(model, d, a) for a in d.ids)
        r = score_ids(pred, d, d.ids)
        ds = delay_summary(r["per_event"])
        rows.append({"scenario": name, "composite": round(r["composite_score"], 1), "recall": round(r["event_recall"], 2), "precision": round(r["alert_precision"], 2),
                     "type recall": round(r["fault_type_recall"], 2), "class recall": round(r["class_recall"], 2), "false+repeat per pump-day": round(r["false_alerts_per_asset_day"], 2),
                     "events": r["events_scored"]})
        print(rows[-1], f"[{time.time() - t0:.0f}s]", flush=True)
    df = pd.DataFrame(rows)
    out = ["# Missing sensors: untouched hold fleets (24 pumps, 82 events), frozen model", "",
           "Whole channels are removed from the data before anything is computed. The model was trained on a mix of full, retrofit and legacy pumps, so it has seen missing channels, but not these removals on top of each tier.", "",
           "| Scenario | Composite | Recall | Precision | Type recall | Class recall | False + repeat per pump-day |", "|---|---|---|---|---|---|---|"]
    out += [f"| {r['scenario']} | {r['composite']} | {r['recall']} | {r['precision']} | {r['type recall']} | {r['class recall']} | {r['false+repeat per pump-day']} |" for r in rows]
    Path(ROOT / "eval" / "results" / "missing_sensor.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    Path(ROOT / "eval" / "results" / "missing_sensor.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
