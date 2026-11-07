#!/usr/bin/env python3
"""Measure what the detector needs on an edge computer: model size, time to score one pump-week on one CPU core, peak memory. Writes eval/results/footprint.json.

  .venv/bin/python eval/footprint.py --model models/wk_final.joblib
Uses a public dev pump only.
"""
import argparse
import json
import platform
import resource
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from watchkeeper.diagnose import DiagnosisModel  # noqa: E402
from watchkeeper.evalkit import ROOT, load_dev  # noqa: E402
from watchkeeper.methods import WKMethod  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(ROOT / "models" / "wk_final.joblib"))
    ap.add_argument("--asset", default="PUMP-08")
    ap.add_argument("--out", default=str(ROOT / "eval" / "results" / "footprint.json"))
    a = ap.parse_args()
    dev = load_dev()
    t = time.perf_counter()
    model = DiagnosisModel.load(a.model)
    t_load = time.perf_counter() - t
    model.model.n_jobs = 1
    sub = dev.__class__(dev.root, dev.assets, dev.feat[dev.feat.asset_id == a.asset].copy(), dev.events.iloc[0:0], dev.benign.iloc[0:0], dev.alarms.iloc[0:0])
    t = time.perf_counter()
    pred = WKMethod().predict(model, sub, a.asset)
    t_pred = time.perf_counter() - t
    minutes = int(len(sub.feat))
    out = {"model_file": Path(a.model).name, "model_mb": round(Path(a.model).stat().st_size / 1e6, 1), "load_s": round(t_load, 2), "asset": a.asset, "minutes_scored": minutes,
           "score_s": round(t_pred, 1), "ms_per_pump_minute": round(1000 * t_pred / max(minutes, 1), 2), "alerts": int(len(pred)),
           "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024 if sys.platform == "darwin" else 1024), 0),
           "python": platform.python_version(), "cpu_only": True, "gpu": False, "network_needed": False, "cores_used": 1}
    Path(a.out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
