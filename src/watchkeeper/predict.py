"""Frozen-pipeline predictions for a list of pumps, written in the organizers' CSV format.

  python -m watchkeeper.predict --assets PUMP-10 PUMP-11 PUMP-12 --out submission/predictions_test.csv

The model is fitted on the labelled dev pumps (PUMP-01..09), never on the pumps being predicted. For a dev pump the fit excludes
that pump, so the output is a held-out prediction and can be scored. The test pumps are read here and nowhere else: this module is the
only place that loads their telemetry, and it never reads labels for them. Run it from a clean, tagged commit; the commit hash and the
dirty flag are written next to the CSV.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import warnings
from pathlib import Path

import pandas as pd

from .alerts.export import write_predictions_csv
from .evalkit import ROOT, DevData, concat_predictions, default_data_dir, load_dev
from .methods import METHODS


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()
    except OSError:
        return ""


def target_data(dev: DevData, asset_ids: list[str]) -> DevData:
    """Telemetry features for the target pumps only. No events, no benign windows, no alarms: nothing label-like is loaded."""
    assets = pd.read_csv(dev.root / "assets.csv")
    unknown = set(asset_ids) - set(assets.asset_id)
    if unknown:
        raise SystemExit(f"unknown assets {sorted(unknown)}")
    feat = pd.read_parquet(dev.root / "features_1min.parquet", filters=[("asset_id", "in", list(asset_ids))])
    empty = pd.DataFrame(columns=["asset_id"])
    return DevData(dev.root, assets, feat, empty, empty, empty)


def predict_assets(asset_ids: list[str], method_name: str = "wk", data_dir=None) -> tuple[pd.DataFrame, list[str]]:
    dev = load_dev(data_dir)
    train_ids = [a for a in dev.ids if a not in set(asset_ids)]
    method = METHODS[method_name]()
    model = method.fit(dev, train_ids)
    tgt = target_data(dev, asset_ids)
    return concat_predictions(method.predict(model, tgt, a) for a in asset_ids), train_ids


def main(argv=None) -> int:
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--assets", nargs="+", required=True)
    ap.add_argument("--method", default="wk", choices=sorted(METHODS))
    ap.add_argument("--data", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--allow-dirty", action="store_true", help="Only for experiments; the meta file records it.")
    a = ap.parse_args(argv)

    dirty = bool(_git("status", "--porcelain"))
    if dirty and not a.allow_dirty:
        raise SystemExit("working tree is not clean. Commit (and tag) first, or pass --allow-dirty for an experiment.")
    pred, train_ids = predict_assets(a.assets, a.method, a.data or default_data_dir())
    out = Path(a.out)
    write_predictions_csv(pred, out)
    meta = {"created_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "commit": _git("rev-parse", "HEAD"),
            "tag": _git("describe", "--tags", "--exact-match") or None, "dirty": dirty, "method": a.method,
            "fitted_on": train_ids, "targets": a.assets, "alerts": int(len(pred))}
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"{len(pred)} alerts for {a.assets} -> {out}  (commit {meta['commit'][:8]}{', DIRTY' if dirty else ''})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
