"""Loader for the bank of simulated fleets written by scripts/make_bank.py. Labels are complete (events_train.csv)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .evalkit import ROOT, DevData

DEFAULT = ROOT / "bank"
SETS = {"train": [201, 202, 203, 204, 205], "tune": [206, 207], "hold": [208, 209, 210], "healthy": [301, 302, 303, 304, 305, 306], "healthy_train": [311, 312, 313, 314, 315, 316]}


def _read(p: Path) -> pd.DataFrame:
    return pd.read_csv(p) if p.exists() and p.stat().st_size > 0 else pd.DataFrame()


def load_set(name: str, seeds=None, bank=None) -> DevData:
    """All pumps of one named set as a DevData. Pump ids look like B201-03 and are unique across the bank."""
    root = Path(bank) if bank else DEFAULT
    parts = {k: [] for k in ("assets", "feat", "events", "benign", "alarms")}
    for s in seeds or SETS[name]:
        pub = root / name / f"s{s}" / "public"
        if not (pub / "features_1min.parquet").exists():
            raise FileNotFoundError(f"{pub} is missing; run `make bank`")
        parts["assets"].append(pd.read_csv(pub / "assets.csv"))
        parts["feat"].append(pd.read_parquet(pub / "features_1min.parquet"))
        parts["events"].append(_read(pub / "events_train.csv"))
        parts["benign"].append(_read(pub / "benign_windows_train_validation.csv"))
        parts["alarms"].append(_read(pub / "alarms.csv"))
    j = {k: pd.concat([x for x in v if len(x)] or [pd.DataFrame(columns=["asset_id"])], ignore_index=True) for k, v in parts.items()}
    if name.startswith("healthy"):                       # pump -01 of each healthy fleet carries the decoy outage; it is not part of the count
        keep = lambda df: df[~df["asset_id"].astype(str).str.endswith("-01")] if len(df) and "asset_id" in df else df
        j = {k: keep(v) for k, v in j.items()}
        j["events"] = j["events"].iloc[0:0]
    if j["events"].empty:
        j["events"] = pd.DataFrame(columns=["event_id", "asset_id", "event_class", "fault_type", "onset_utc", "detectable_utc", "action_deadline_utc",
                                            "end_utc", "observable"])
    return DevData(root, j["assets"], j["feat"], j["events"], j["benign"], j["alarms"])


def load_trap(bank=None) -> DevData:
    pub = (Path(bank) if bank else DEFAULT) / "trap" / "public"
    return DevData(pub, pd.read_csv(pub / "assets.csv"), pd.read_parquet(pub / "features_1min.parquet"), pd.read_csv(pub / "events_train.csv"),
                   _read(pub / "benign_windows_train_validation.csv"), _read(pub / "alarms.csv"))


def combine(*sets: DevData) -> DevData:
    cat = lambda name: pd.concat([getattr(s, name) for s in sets if len(getattr(s, name))], ignore_index=True)
    return DevData(sets[0].root, cat("assets"), cat("feat"), cat("events"), cat("benign"), cat("alarms"))
