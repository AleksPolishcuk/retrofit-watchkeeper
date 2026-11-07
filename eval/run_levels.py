#!/usr/bin/env python3
"""Back-test table behind the stage words (Watch, Possible, Likely, Very likely): of the alerts that fell in each confidence band, how many pointed at a real event
and how many named the right fault type. Written to models/stages.json and shown to the operator as counts, never as a percentage that claims calibration.

  .venv/bin/python eval/run_levels.py --model models/wk.joblib --sets tune dev9
Uses alerts on fleets whose labels the model never saw (default tune and the 9 dev pumps). Never reads the hold fleets or the test pumps.
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

from watchkeeper.bank import load_set  # noqa: E402
from watchkeeper.diagnose import DiagnosisModel  # noqa: E402
from watchkeeper.evalkit import ROOT, alert_outcomes, concat_predictions, load_dev  # noqa: E402
from watchkeeper.methods import WKMethod  # noqa: E402
from watchkeeper.stage import EDGES, STAGES, stage_of  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(ROOT / "models" / "wk.joblib"))
    ap.add_argument("--sets", nargs="+", default=["tune", "dev9"])
    ap.add_argument("--out", default=str(ROOT / "models" / "stages.json"))
    ap.add_argument("--sig-h", type=float, default=None)
    ap.add_argument("--slow-h", type=float, default=None)
    a = ap.parse_args()
    model = DiagnosisModel.load(a.model)
    wk = WKMethod(trees=60, sig_h=a.sig_h, slow_h=a.slow_h)
    frames = []
    for name in a.sets:
        d = load_dev() if name == "dev9" else load_set(name)
        pred = concat_predictions(wk.predict(model, d, x) for x in d.ids)
        if len(pred):
            frames.append(alert_outcomes(pred, d))
    al = pd.concat(frames, ignore_index=True)
    al["stage"] = [stage_of(float(c), EDGES) for c in al["confidence"]]
    basis, detail = {}, {}
    source = "back-test on simulated fleets " + "+".join(a.sets)
    for st in STAGES:
        s = al[al["stage"] == st]
        basis[st] = {"n": int(len(s)), "correct": int(s["type_ok"].sum()), "source": source}          # matches stage_basis in docs/alert.schema.json
        detail[st] = {"alerts": int(len(s)), "at_a_real_event": int(s["in_event"].sum()), "right_class": int(s["class_ok"].sum()), "right_type": int(s["type_ok"].sum())}
    out = {"edges": list(EDGES), "sets": a.sets, "model": Path(a.model).name, "signature": {"sig_h": a.sig_h, "slow_h": a.slow_h}, "basis": basis, "detail": detail,
           "note": "Counts from back-testing on simulated fleets the model was not trained on. They describe this simulator, not field performance."}
    Path(a.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(pd.DataFrame(detail).T.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
