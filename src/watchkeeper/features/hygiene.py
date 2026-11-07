"""Input hygiene for one-minute telemetry features: repeated minutes, order, and what was done about them.

Scenarios A14 and P04 of the enterprise verification: a gateway can deliver the same minute twice (retry, replay) and rows can arrive out of order.
The detector must neither crash nor silently pick a value. Repeated rows with identical values are dropped; repeated rows with different values keep the last
delivered one and are counted as conflicts so that the operator can be told. Clean data are returned untouched (the same object).
"""
from __future__ import annotations

import pandas as pd

KEY = ["asset_id", "window_start_utc"]


def clean_minutes(feat: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Returns (features, report). The report counts rows in, exact duplicates dropped, conflicting duplicates (last one kept) and rows that were out of order."""
    report = {"rows_in": int(len(feat)), "duplicates_dropped": 0, "conflicts": 0, "out_of_order": 0}
    if feat.empty or not set(KEY) <= set(feat.columns):
        return feat, report
    dup = feat.duplicated(KEY, keep=False)
    t = pd.to_datetime(feat["window_start_utc"], utc=True)
    out_of_order = int((t.groupby(feat["asset_id"]).diff().dt.total_seconds() < 0).sum())
    report["out_of_order"] = out_of_order
    if not dup.any():
        return feat, report
    value_cols = [c for c in feat.columns if c not in KEY]
    d = feat[dup]
    # a repeated minute is a conflict when its copies are not all identical
    n_unique = d.drop_duplicates(KEY + value_cols).groupby(KEY).size()
    report["conflicts"] = int((n_unique > 1).sum())
    report["duplicates_dropped"] = int(feat.duplicated(KEY, keep="last").sum())
    cleaned = feat.drop_duplicates(KEY, keep="last").sort_values(KEY, kind="stable").reset_index(drop=True)
    return cleaned, report
