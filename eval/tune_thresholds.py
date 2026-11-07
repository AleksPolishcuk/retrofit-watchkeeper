#!/usr/bin/env python3
"""Choose the trigger threshold k and the persistence on the TUNE fleets only. Dev pumps are shown as a check, hold fleets are never read.

  .venv/bin/python eval/tune_thresholds.py --model models/wk.joblib
"""
import argparse
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(ROOT / "models" / "wk.joblib"))
    ap.add_argument("--out", default=str(ROOT / "eval" / "results" / "tuning.md"))
    a = ap.parse_args()
    model = DiagnosisModel.load(a.model)
    sets = {"tune": load_set("tune"), "dev9": load_dev(), "trap": load_trap()}
    rows, t0 = [], time.time()
    for k in (4.0, 5.0, 6.0, 8.0):
        for persist in (6, 8, 12, 15):
            wk = M.WKMethod(k=k, persist=persist)
            row = {"k": k, "persist": persist}
            for name, d in sets.items():
                pred = concat_predictions(wk.predict(model, d, x) for x in d.ids)
                r = score_ids(pred, d, d.ids)
                row[f"{name} composite"] = round(r["composite_score"], 1)
                row[f"{name} FA/day"] = round(r["false_alerts_per_asset_day"], 2)
                if name == "tune":
                    row["tune recall"], row["tune type"] = round(r["event_recall"], 2), round(r["fault_type_recall"], 2)
            rows.append(row)
            print(row, f"[{time.time() - t0:.0f}s]", flush=True)
    df = pd.DataFrame(rows)
    ok = df[df["tune FA/day"] <= 0.10]
    best = (ok if len(ok) else df).sort_values("tune composite", ascending=False).iloc[0]
    md = ["# Trigger tuning (k, persistence)", "", "Chosen on the tune fleets only, among settings with at most 0.10 false + repeat alerts per pump-day. Dev pumps and the trap are shown as a check.", "",
          df.to_markdown(index=False), "", f"**Chosen: k={best.k:g}, persistence={int(best.persist)} minutes** (tune composite {best['tune composite']})."]
    Path(a.out).write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"chosen k={best.k:g} persist={int(best.persist)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
