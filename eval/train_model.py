#!/usr/bin/env python3
"""Fit the diagnosis model on the bank (and optionally the dev pumps) and save it.

  .venv/bin/python eval/train_model.py --fit train --out models/wk.joblib
Never reads the test pumps.
"""
import argparse
import sys
import time
import warnings

warnings.filterwarnings("ignore")

from watchkeeper.bank import combine, load_set  # noqa: E402
from watchkeeper.evalkit import ROOT, load_dev  # noqa: E402
from watchkeeper.methods import WKMethod  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", choices=["train", "train+tune", "train+tune+dev"], default="train")
    ap.add_argument("--out", default=str(ROOT / "models" / "wk.joblib"))
    ap.add_argument("--trees", type=int, default=60)
    ap.add_argument("--min-leaf", type=int, default=25)
    ap.add_argument("--max-depth", type=int, default=14)
    ap.add_argument("--no-healthy", action="store_true", help="leave out the healthy_train fleets (examples of normal operation, labelled NONE)")
    a = ap.parse_args()
    t0 = time.time()
    sets = [load_set("train")] + ([] if a.no_healthy else [load_set("healthy_train")]) + ([load_set("tune")] if "tune" in a.fit else []) + ([load_dev()] if a.fit.endswith("dev") else [])
    data = combine(*sets)
    m = WKMethod(trees=a.trees, min_leaf=a.min_leaf, max_depth=(a.max_depth or None))
    model = m.fit(data, data.ids)
    size = model.save(a.out)
    print(f"fitted on {len(data.ids)} pumps ({a.fit}) in {time.time() - t0:.0f} s; model {size / 1e6:.1f} MB -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
