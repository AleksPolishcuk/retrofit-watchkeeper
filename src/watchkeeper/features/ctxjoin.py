"""Operating context (cooling demand, water and ambient temperature) joined to the one-minute features.

The context table is plant-level information that exists for every pump in the data pack, including the test pumps; it holds no labels.
Joined columns are prefixed `ctx_`. A missing file or a missing pump leaves the features unchanged.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

CTX_COLUMNS = ["duty_demand_pct", "supply_water_temp_c", "ambient_temp_c", "sea_temp_c"]


def attach_context(feat: pd.DataFrame, ctx_path, asset_ids=None) -> pd.DataFrame:
    p = Path(ctx_path)
    if not p.exists() or feat.empty:
        return feat
    ctx = pd.read_csv(p, usecols=["asset_id", "timestamp_utc"] + [c for c in CTX_COLUMNS])
    ids = set(asset_ids) if asset_ids is not None else set(feat["asset_id"])
    ctx = ctx[ctx["asset_id"].isin(ids)].copy()
    if ctx.empty:
        return feat
    ctx["_t"] = pd.to_datetime(ctx["timestamp_utc"], utc=True, format="ISO8601")
    ctx = ctx.drop(columns="timestamp_utc").rename(columns={c: "ctx_" + c for c in CTX_COLUMNS})
    out = feat.copy()
    out["_t"] = pd.to_datetime(out["window_start_utc"], utc=True, format="ISO8601")
    out = out.merge(ctx, on=["asset_id", "_t"], how="left").drop(columns="_t")
    return out
