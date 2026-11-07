#!/usr/bin/env python3
"""Turn the submitted test-pump CSV into contract alerts for the interface (artifacts/alerts/<pump>.json). Reads the CSV and the asset table only: the model is not run again.

  .venv/bin/python scripts/export_submitted_alerts.py
"""
import json
import sys
import warnings

import pandas as pd

warnings.filterwarnings("ignore")

from watchkeeper.alerts import archive_alerts, to_contract, write_alerts  # noqa: E402
from watchkeeper.evalkit import ROOT, default_data_dir  # noqa: E402


def main() -> int:
    meta = json.loads((ROOT / "submission" / "predictions_test.meta.json").read_text(encoding="utf-8"))
    pred = pd.read_csv(ROOT / "submission" / "predictions_test.csv")
    assets = pd.read_csv(default_data_dir() / "assets.csv")
    alerts = to_contract(pred, assets, source="WK_causal_learned (submitted predictions)", model_version="wk-" + meta["model_sha256"][:10])
    paths = write_alerts(alerts, ROOT / "artifacts" / "alerts", meta["targets"])
    archived = archive_alerts(alerts, ROOT / "artifacts" / "alerts_archive")
    print(f"{len(alerts)} alerts for {meta['targets']} ->", ", ".join(p.name for p in paths), f"({len(archived)} new snapshot(s) archived)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
