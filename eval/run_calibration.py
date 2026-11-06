#!/usr/bin/env python3
"""Check how well the raw alert score predicts a correct diagnosis, and fit a calibrator only if it clearly helps.

  .venv/bin/python eval/run_calibration.py
Uses only the nine dev pumps (leave-one-asset-out predictions). Never reads the test pumps.
A calibrator is saved to models/calibrator.json only if its nested Brier score beats the raw score by at least MIN_GAIN.
"""
import sys
import time
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

from watchkeeper.calibrate import DEFAULT_PATH, Calibrator, brier, nested_calibration, reliability  # noqa: E402
from watchkeeper.evalkit import alert_outcomes, load_dev, run_loo  # noqa: E402
from watchkeeper.methods import WKMethod  # noqa: E402

OUT = Path(__file__).resolve().parent / "results" / "calibration.md"
MIN_GAIN = 0.01


def main() -> int:
    t0 = time.time()
    data = load_dev()
    pred = alert_outcomes(run_loo(WKMethod(), data)["predictions"], data)
    pred.to_csv(OUT.parent / "WK_causal_learned" / "alerts_loo_outcomes.csv", index=False)
    y = pred["type_ok"].to_numpy().astype(float)
    raw = pred["confidence"].to_numpy().astype(float)

    base = brier(np.full(len(y), y.mean()), y)
    raw_brier = brier(raw, y)
    tab_raw, ece_raw = reliability(raw, y)
    cands = []
    for C in (0.3, 1.0, 5.0):
        p = nested_calibration(pred, C=C)
        cands.append((C, brier(p, y), reliability(p, y)[1]))
    best = min(cands, key=lambda c: c[1])
    use = best[1] < raw_brier - MIN_GAIN

    L = [f"# Confidence calibration\n\nLeave-one-asset-out alerts of the `wk` method on the 9 dev pumps: {len(pred)} alerts, "
         f"{int(y.sum())} with the right fault type ({y.mean():.0%}), {int(pred.in_event.sum())} inside a labelled event.\n",
         "Target: the probability that the fault type named in the alert matches a labelled event active at that time.\n",
         "| Score | Brier (lower is better) | Expected calibration error |", "|---|---|---|",
         f"| **raw score used as a probability (shipped)** | {raw_brier:.3f} | {ece_raw:.3f} |",
         f"| constant base rate ({y.mean():.2f}) | {base:.3f} | 0.000 |"]
    L += [f"| learned calibrator, C={c}, each pump held out | {b:.3f} | {e:.3f} |" for c, b, e in cands]
    L += ["", "## Reliability of the raw score", "", "| Predicted | Alerts | Mean predicted | Observed correct |", "|---|---|---|---|"]
    L += [f"| {r.bin} | {r.n} | {r.mean_predicted:.2f} | {r.observed:.2f} |" for r in tab_raw.itertuples()]
    by = pred.groupby(pred["rule"].fillna("model")).agg(n=("type_ok", "size"), raw=("confidence", "mean"), observed=("type_ok", "mean"))
    L += ["", "## By source of the alert", "", "| Source | Alerts | Mean raw score | Observed correct |", "|---|---|---|---|"]
    L += [f"| {i} | {int(r.n)} | {r.raw:.2f} | {r.observed:.2f} |" for i, r in by.iterrows()]
    L += ["", "## Decision", "",
          (f"A learned calibrator (C={best[0]}) beats the raw score by {raw_brier - best[1]:.3f} Brier and is saved to `models/calibrator.json`."
           if use else
           f"No learned calibrator beats the raw score by {MIN_GAIN} Brier (best {best[1]:.3f} against {raw_brier:.3f}). With about {len(pred)} alerts a "
           "logistic calibrator only adds noise, so the raw score is shipped as the confidence. Rule-based instrument alerts are the weakest "
           "(see the table by source), and the cockpit shows the alternatives next to the main diagnosis."),
          "", "Caveat: this is a small sample, and the test pumps are a new vessel and a new plant, so calibration may shift there."]
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    if use:
        Calibrator(best[0]).fit(pred, "type_ok", fitted_on=data.ids).save(DEFAULT_PATH)
    elif DEFAULT_PATH.exists():
        DEFAULT_PATH.unlink()
    print("\n".join(L[4:11]))
    print(f"{'calibrator saved' if use else 'no calibrator saved (raw score shipped)'}; report -> {OUT} ({time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
