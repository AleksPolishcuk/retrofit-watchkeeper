#!/usr/bin/env python3
"""Score a method on train, validation and leave-one-asset-out over the 9 dev pumps. Never reads the test pumps.

  .venv/bin/python eval/run_eval.py --method b1
"""
import argparse
import sys
import time
import warnings
from pathlib import Path

import pandas as pd

from watchkeeper.evalkit import load_dev, markdown_table, run_fixed_split, run_loo
from watchkeeper.methods import METHODS

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=FutureWarning)      # noise from the organizer baseline code


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", required=True, choices=sorted(METHODS))
    ap.add_argument("--data", default=None, help="Folder with the full dataset (default: ./data)")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "results"))
    a = ap.parse_args(argv)

    t0 = time.time()
    data = load_dev(a.data)
    print(f"dev assets: {data.ids}")
    method = METHODS[a.method]()
    fixed = run_fixed_split(method, data)
    loo = run_loo(method, data)

    rows = {"fit on train / train": fixed["train"], "fit on train / validation": fixed["validation"],
            "leave-one-asset-out / all 9": loo["all"]}
    table = markdown_table(rows)
    print(table)

    out = Path(a.out) / (method.name + ("" if getattr(method, "rules", True) else "_no_rules") + ("" if getattr(method, "arbiter", True) else "_no_arbiter"))
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(loo["all"]["per_event"]).to_csv(out / "per_event_loo.csv", index=False)
    loo["predictions"].to_csv(out / "predictions_loo.csv", index=False)
    (out / "summary.md").write_text(
        f"# {method.name}\n\nFixed split: fitted on the train pumps. The train row is in-sample; read validation and leave-one-asset-out.\n\n"
        f"Leave-one-asset-out: {len(loo['folds'])} folds, each fitted on the other eight pumps.\n\n"
        f"{table}\n", encoding="utf-8")
    print(f"written to {out} in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
