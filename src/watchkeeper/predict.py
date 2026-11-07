"""Frozen-pipeline predictions for a list of pumps, written in the organizers' CSV format.

  python -m watchkeeper.predict --assets PUMP-10 PUMP-11 PUMP-12 --out submission/predictions_test.csv

The model is the frozen file produced by `eval/train_model.py` (fitted on simulated fleets and the labelled dev pumps PUMP-01..09), never on
the pumps being predicted. Nothing is trained here. The test pumps are read here and nowhere else: this module is the only place that loads
their telemetry, and it never reads labels for them. Run it from a clean, tagged commit; the commit hash, the dirty flag and the model file's
hash are written next to the CSV.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
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


def predict_assets(asset_ids: list[str], model_path, method_name: str = "wk", data_dir=None) -> pd.DataFrame:
    from .diagnose import DiagnosisModel
    dev = load_dev(data_dir)
    method = METHODS[method_name]()
    model = DiagnosisModel.load(model_path)
    tgt = target_data(dev, asset_ids)
    return concat_predictions(method.predict(model, tgt, a) for a in asset_ids)


def main(argv=None) -> int:
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--assets", nargs="+", required=True)
    ap.add_argument("--method", default="wk", choices=sorted(METHODS))
    ap.add_argument("--model", default=str(ROOT / "models" / "wk_final.joblib"))
    ap.add_argument("--data", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--allow-dirty", action="store_true", help="Only for experiments; the meta file records it.")
    a = ap.parse_args(argv)

    dirty = bool(_git("status", "--porcelain"))
    if dirty and not a.allow_dirty:
        raise SystemExit("working tree is not clean. Commit (and tag) first, or pass --allow-dirty for an experiment.")
    model_file = Path(a.model)
    pred = predict_assets(a.assets, model_file, a.method, a.data or default_data_dir())
    out = Path(a.out)
    write_predictions_csv(pred, out)
    meta = {"created_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "commit": _git("rev-parse", "HEAD"),
            "tag": _git("describe", "--tags", "--exact-match") or None, "dirty": dirty, "method": a.method,
            "model_file": model_file.name, "model_sha256": hashlib.sha256(model_file.read_bytes()).hexdigest(), "targets": a.assets, "alerts": int(len(pred))}
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"{len(pred)} alerts for {a.assets} -> {out}  (commit {meta['commit'][:8]}{', DIRTY' if dirty else ''})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
