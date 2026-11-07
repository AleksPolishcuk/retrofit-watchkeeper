#!/usr/bin/env python3
"""Write contract alerts for dev pumps to artifacts/alerts/<asset_id>.json (read by the API). Never touches the test pumps.

  .venv/bin/python eval/export_alerts.py --method b1
  .venv/bin/python eval/export_alerts.py --method wk --model models/wk.joblib   # frozen model that was not trained on the dev pumps: held-out alerts
"""
import argparse
import hashlib
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from watchkeeper.alerts import to_contract, write_alerts  # noqa: E402
from watchkeeper.evalkit import ROOT, load_dev  # noqa: E402
from watchkeeper.methods import METHODS  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", required=True, choices=sorted(METHODS))
    ap.add_argument("--assets", nargs="*", default=None, help="Dev pumps to export (default: all nine)")
    ap.add_argument("--model", default=None, help="frozen diagnosis model file (method wk); without it the method is fitted on the train pumps")
    ap.add_argument("--data", default=None)
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "alerts"))
    a = ap.parse_args(argv)

    data = load_dev(a.data)
    ids = a.assets or data.ids
    unknown = set(ids) - set(data.ids)
    if unknown:
        raise SystemExit(f"not dev pumps: {sorted(unknown)}")
    method = METHODS[a.method]()
    if a.model:
        from watchkeeper.diagnose import DiagnosisModel
        params, version = DiagnosisModel.load(a.model), "wk-" + hashlib.sha256(Path(a.model).read_bytes()).hexdigest()[:10]
    else:
        params, version = method.fit(data, data.ids_of("train")), "unversioned"          # fitted on the train pumps only
    pred = method.predict_many(params, data, ids)
    alerts = to_contract(pred, data.assets, source=method.name, model_version=version)
    paths = write_alerts(alerts, a.out, ids)
    print(f"{method.name} model={version}: {len(alerts)} alerts for {len(ids)} pumps -> {Path(a.out)}")
    for p in paths:
        print(" ", p.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
