#!/usr/bin/env python3
"""Rebuild docs/business_case.md from the untouched hold fleets and the frozen model (models/wk.joblib, not trained on them).

  .venv/bin/python eval/run_business_case.py
Measured inputs: event recall, share found before the conventional limit, false and repeat alerts per pump-day. Money inputs stay assumptions.
"""
import json
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

from watchkeeper import business_case as BC  # noqa: E402
from watchkeeper.bank import load_set  # noqa: E402
from watchkeeper.diagnose import DiagnosisModel  # noqa: E402
from watchkeeper.evalkit import ROOT, concat_predictions, score_ids  # noqa: E402
from watchkeeper.methods import WKMethod  # noqa: E402


def main() -> int:
    model = DiagnosisModel.load(ROOT / "models" / "wk.joblib")
    hold = load_set("hold")
    wk = WKMethod()
    r = score_ids(concat_predictions(wk.predict(model, hold, a) for a in hold.ids), hold, hold.ids)
    out = ROOT / "eval" / "results" / "WK_hold"
    out.mkdir(parents=True, exist_ok=True)
    pe = pd.DataFrame(r.pop("per_event"))
    pe.to_csv(out / "per_event.csv", index=False)
    (out / "metrics.json").write_text(json.dumps({"leave_one_asset_out": r}, indent=2, default=float), encoding="utf-8")
    hold.assets.to_csv(out / "assets.csv", index=False)
    text = BC.build(out / "metrics.json", out / "per_event.csv", out / "assets.csv", source="the 24 untouched hold fleets, 82 events, model not trained on them")
    BC.OUT.write_text(text, encoding="utf-8")
    print(text[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
