#!/usr/bin/env python3
"""For every labelled event that got an alert: which fault type did the alert name, and which rule produced it?

  .venv/bin/python eval/probes/type_confusion.py [--model models/wk.joblib] [--sets tune dev9 trap]
The first in-window alert of an event decides (the organizer scorer credits the type of the first matching burst). Never reads hold fleets or test pumps.
"""
import argparse
import sys
import warnings

import pandas as pd

warnings.filterwarnings("ignore")

from watchkeeper.bank import load_set, load_trap  # noqa: E402
from watchkeeper.diagnose import DiagnosisModel  # noqa: E402
from watchkeeper.evalkit import ROOT, alert_outcomes, concat_predictions, load_dev  # noqa: E402
from watchkeeper.methods import WKMethod  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(ROOT / "models" / "wk.joblib"))
    ap.add_argument("--sets", nargs="+", default=["tune", "dev9", "trap"])
    ap.add_argument("--drop", nargs="*", default=[])
    a = ap.parse_args()
    model = DiagnosisModel.load(a.model)
    wk = WKMethod(trees=60, drop=tuple(a.drop))
    rows = []
    for name in a.sets:
        d = load_dev() if name == "dev9" else load_trap() if name == "trap" else load_set(name)
        pred = concat_predictions(wk.predict(model, d, x) for x in d.ids)
        if not len(pred):
            continue
        al = alert_outcomes(pred, d)
        al["t"] = pd.to_datetime(al["alert_time_utc"], utc=True, format="ISO8601")
        for e in d.events[d.events["observable"].astype(str).str.lower().isin(["true", "1"])].itertuples():
            hit = al[(al.asset_id == e.asset_id) & al.matched_types.str.contains(e.fault_type, regex=False)].sort_values("t")
            first = hit.iloc[0] if len(hit) else None
            any_in = al[(al.asset_id == e.asset_id) & al.in_event & al.matched_types.str.contains(e.fault_type, regex=False)]
            rows.append({"set": name, "true": e.fault_type, "class": e.event_class, "alerted": first is not None,
                         "named": None if first is None else first.fault_type, "rule": None if first is None else first.get("rule"),
                         "evidence": None if first is None else str(first.evidence)[:90]})
    df = pd.DataFrame(rows)
    det = df[df.alerted]
    print("events:", len(df), " with a matching alert:", len(det), " type right:", int((det["true"] == det["named"]).sum()))
    print("\nconfusion (rows: true type, columns: type named by the alert that matched the event)")
    print(pd.crosstab(det["true"], det["named"]).to_string())
    print("\nby set:")
    print(det.assign(ok=det["true"] == det["named"]).groupby("set")["ok"].agg(["sum", "count"]).to_string())
    print("\nundetected by true type:")
    print(df[~df.alerted]["true"].value_counts().to_string())
    print("\nwrong-type alerts, first channels in the evidence:")
    print(det[det["true"] != det["named"]][["set", "true", "named", "rule", "evidence"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
