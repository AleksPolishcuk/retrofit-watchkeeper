#!/usr/bin/env python3
"""Where do healthy simulated pumps sit away from their own causal baseline? Per pump and channel: share of steady minutes after the baseline period with |z| > 3
and the median z, joined with the pump's properties. The healthy_train fleets have no faults, so every large value is baseline error or regime effect.

  .venv/bin/python eval/probes/healthy_bias.py
"""
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from watchkeeper import methods as M  # noqa: E402
from watchkeeper.bank import load_set  # noqa: E402
from watchkeeper.features.causal import KEYS  # noqa: E402


def main() -> int:
    d = load_set("healthy_train")
    zf = M._zf(d, True, 60, 6)
    assets = d.assets.set_index("asset_id")
    rows = []
    for a, g in zf.groupby("asset_id"):
        g = g[g["window_start_utc"] >= g["window_start_utc"].min() + pd.Timedelta(hours=24)]
        st = g[g["steady"]]
        r = {"asset": a, "steady_min": len(st)}
        for k in KEYS:
            if f"z_{k}" in st and st[f"z_{k}"].notna().sum() > 100:
                z = st[f"z_{k}"].dropna()
                r[f"{k}>3"] = round(float((z.abs() > 3).mean()), 3)
                r[f"{k}_med"] = round(float(z.median()), 2)
        rows.append(r)
    df = pd.DataFrame(rows).set_index("asset")
    cols = [c for c in df.columns if c.endswith(">3")]
    df["worst"] = df[cols].max(axis=1)
    df["worst_ch"] = df[cols].idxmax(axis=1).str.replace(">3", "")
    props = [c for c in ("drive_type", "control_mode", "instrumentation_tier", "service", "asset_type", "pump_type") if c in assets]
    out = df.join(assets[props]).sort_values("worst", ascending=False)
    pd.set_option("display.width", 250)
    print(out[["worst", "worst_ch", "steady_min"] + props].head(25).to_string())
    print("\nshare of pumps with worst channel above 5 percent of minutes beyond 3 sigma:", round(float((out.worst > 0.05).mean()), 2))
    print("\nby channel, number of pumps above 5 percent:")
    print((df[cols] > 0.05).sum().sort_values(ascending=False).head(8).to_string())
    for p in props:
        print(f"\n{p}:")
        print(out.groupby(p)["worst"].agg(["count", "median", "max"]).round(3).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
