"""Evaluation kit: dev data only (train + validation), organizer scorer, fixed-split and leave-one-asset-out runs.

The test pumps (PUMP-10, 11, 12) are never loaded here. Features are read with a parquet filter, so their rows do not
enter memory, and the loader refuses to return anything that belongs to a test asset.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

import pandas as pd
from retrofit_sim.scoring import score

ROOT = Path(__file__).resolve().parents[2]
DEV_SPLITS = ("train", "validation")
PRED_COLS = ["asset_id", "alert_time_utc", "event_class", "fault_type", "confidence", "evidence", "recommended_action"]
METRICS = ["composite_score", "event_f1", "event_recall", "alert_precision", "false_alerts_per_asset_day", "timeliness",
           "fault_type_recall", "class_recall", "recall_machine", "recall_sensor", "median_lead_time_h"]


def default_data_dir() -> Path:
    return Path(os.environ.get("WATCHKEEPER_DATA", ROOT / "data"))


@dataclass
class DevData:
    root: Path
    assets: pd.DataFrame
    feat: pd.DataFrame
    events: pd.DataFrame
    benign: pd.DataFrame
    alarms: pd.DataFrame
    cache: dict = field(default_factory=dict)

    @property
    def ids(self) -> list[str]:
        return sorted(self.assets.asset_id)

    def ids_of(self, split: str) -> list[str]:
        return sorted(self.assets[self.assets.split == split].asset_id)


def load_dev(data_dir=None) -> DevData:
    root = Path(data_dir) if data_dir else default_data_dir()
    assets_all = pd.read_csv(root / "assets.csv")
    dev = assets_all[assets_all.split.isin(DEV_SPLITS)].reset_index(drop=True)
    ids = sorted(dev.asset_id)
    test_ids = set(assets_all[assets_all.split == "test"].asset_id)
    feat = pd.read_parquet(root / "features_1min.parquet", filters=[("asset_id", "in", ids)])
    events = pd.concat([pd.read_csv(root / "events_train.csv"), pd.read_csv(root / "events_validation.csv")], ignore_index=True)
    benign = pd.read_csv(root / "benign_windows_train_validation.csv")
    alarms = pd.read_csv(root / "alarms.csv")
    alarms = alarms[alarms.asset_id.isin(ids)].reset_index(drop=True)
    for name, df in (("features", feat), ("events", events), ("benign", benign), ("alarms", alarms)):
        leaked = set(df.asset_id) & test_ids
        if leaked:
            raise RuntimeError(f"{name} contains test assets {sorted(leaked)}; evaluation must not touch the test pumps")
    return DevData(root, dev, feat, events, benign, alarms)


def empty_predictions() -> pd.DataFrame:
    return pd.DataFrame(columns=PRED_COLS)


def concat_predictions(frames) -> pd.DataFrame:
    frames = [f for f in frames if len(f)]
    return pd.concat(frames, ignore_index=True) if frames else empty_predictions()


def score_ids(pred: pd.DataFrame, data: DevData, ids, label: str | None = None) -> dict:
    ids = list(ids)
    assets = data.assets[data.assets.asset_id.isin(ids)]
    events = data.events[data.events.asset_id.isin(ids)]
    # `split=None` on purpose: the scorer's `split` filters assets by their dataset split, and we already chose the assets.
    result = score(pred, events, assets, data.benign, split=None)
    result["split"] = label
    return result


class Method:
    """A detector. `fit` returns parameters learned from the given assets only. `predict` is per asset."""

    name = "base"

    def fit(self, data: DevData, train_ids: list[str]):
        raise NotImplementedError

    def predict(self, params, data: DevData, asset_id: str) -> pd.DataFrame:
        raise NotImplementedError

    def predict_many(self, params, data: DevData, ids) -> pd.DataFrame:
        return concat_predictions(self.predict(params, data, a) for a in ids)


def run_fixed_split(method: Method, data: DevData) -> dict:
    """Organizer protocol: fit on the train assets, score train and validation."""
    train_ids, val_ids = data.ids_of("train"), data.ids_of("validation")
    params = method.fit(data, train_ids)
    return {"params": params,
            "train": score_ids(method.predict_many(params, data, train_ids), data, train_ids, "train"),
            "validation": score_ids(method.predict_many(params, data, val_ids), data, val_ids, "validation")}


def run_loo(method: Method, data: DevData) -> dict:
    """Leave one asset out: fit on the other dev assets, predict the held-out one, then score all dev assets together."""
    frames, folds = [], {}
    for held in data.ids:
        rest = [a for a in data.ids if a != held]
        params = method.fit(data, rest)
        folds[held] = params
        frames.append(method.predict(params, data, held))
    pred = concat_predictions(frames)
    return {"folds": folds, "predictions": pred, "all": score_ids(pred, data, data.ids, "leave_one_asset_out")}


def metrics_row(result: dict) -> dict:
    return {m: result.get(m) for m in METRICS} | {"events_scored": result["events_scored"], "alerts": result["alerts_scored"]}


def markdown_table(rows: dict[str, dict]) -> str:
    def f(x, d=2):
        return "-" if x is None or (isinstance(x, float) and pd.isna(x)) else f"{x:.{d}f}"
    head = ("| Run | Composite | F1 | Recall | Precision | FA / asset-day | Timeliness | Type recall | Class recall | Machine recall | Sensor recall | Events |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|")
    lines = [head]
    for name, r in rows.items():
        lines.append(f"| {name} | {f(r['composite_score'], 1)} | {f(r['event_f1'])} | {f(r['event_recall'])} | {f(r['alert_precision'])} | "
                     f"{f(r['false_alerts_per_asset_day'])} | {f(r['timeliness'])} | {f(r['fault_type_recall'])} | {f(r['class_recall'])} | "
                     f"{f(r['recall_machine'])} | {f(r['recall_sensor'])} | {r['events_scored']} |")
    return "\n".join(lines)


def check_causality(method: Method, params, data: DevData, asset_id: str, cut_hours) -> list[str]:
    """Cut the asset's telemetry `h` hours after the window start, re-run, and compare the alerts raised up to the cut with
    the full run. Returns a list of problems (empty means causal for these cuts)."""
    feat = data.feat[data.feat.asset_id == asset_id].copy()
    ts = pd.to_datetime(feat["window_start_utc"], utc=True)
    t0 = ts.min()
    full = method.predict(params, data, asset_id)
    problems = []
    for h in cut_hours:
        cut = t0 + pd.Timedelta(hours=h)
        sub = replace(data, feat=feat[ts < cut], cache={})
        part = method.predict(params, sub, asset_id)
        def upto(df):
            t = pd.to_datetime(df["alert_time_utc"], utc=True) if len(df) else pd.Series([], dtype="datetime64[ns, UTC]")
            return df[t <= cut][["alert_time_utc", "event_class", "fault_type"]].reset_index(drop=True) if len(df) else df
        a, b = upto(full), upto(part)
        if len(a) != len(b) or (len(a) and not a.equals(b)):
            problems.append(f"{asset_id}: cut at {h} h gives {len(b)} alerts up to the cut, the full run gives {len(a)}")
    return problems
