"""Live replay: telemetry messages -> finished minutes -> detector -> alerts and data health on disk.

  python -m watchkeeper.ingest.live --asset PUMP-06 --start 2025-10-06T00:00:00Z --end 2025-10-07T00:00:00Z --speed 3600
  python -m retrofit_sim replay --data data --asset PUMP-06 | python -m watchkeeper.ingest.live --asset PUMP-06 --input -

Read-only. The runner reads messages and writes `artifacts/live/<asset>/state.json`; the API only reads that file. Nothing is published to a
broker or a device and no command topic is read.

The detector is causal: an alert at time t uses only minutes up to t (tested by truncation). So the runner can re-run the pipeline on the
minutes received so far, every `--every` minutes, and publish the alerts that are new. The alerts after the last re-run equal the alerts of
one batch run over the same minutes (tests/test_ingest.py). The cost is re-evaluating the history received so far, which grows with the
stream: the measured evaluation time is written to the state file with the as-of time of every alert, so the delay is visible, not claimed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from ..alerts import to_contract
from ..detect.datahealth import data_health
from ..detect.rangecheck import check_ranges
from ..evalkit import ROOT, DevData, default_data_dir
from ..features.hygiene import clean_minutes
from .aggregate import MinuteAggregator, rows_to_frame


def _utc(t):
    if t is None:
        return None
    t = pd.Timestamp(t)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _iso(t) -> str:
    return pd.Timestamp(t).strftime("%Y-%m-%dT%H:%M:%SZ")


class LiveRunner:
    def __init__(self, asset_id: str, assets: pd.DataFrame, model, out_dir=None, every: int = 15, lateness_s: float = 5.0,
                 method=None, model_version: str = "unversioned", source: str = "live replay", fine_from=None, fine_every: int = 1, fine_to=None):
        from ..methods import METHODS
        self.asset_id, self.assets, self.model = asset_id, assets, model
        self.asset_row = assets.set_index("asset_id").loc[asset_id].copy()
        self.asset_row["asset_id"] = asset_id
        self.every, self.version, self.source = int(every), model_version, source
        self.fine_from, self.fine_to = _utc(fine_from), _utc(fine_to)
        self.fine_every = int(fine_every)
        self.method = method or METHODS["wk"]()
        channels = str(self.asset_row.get("channels_available", "")).split("|")
        self.agg = MinuteAggregator(lateness_s=lateness_s, channels={asset_id: [c for c in channels if c]})
        self.out = Path(out_dir) / asset_id if out_dir else None
        self.rows: list[dict] = []
        self.since_eval = 0
        self.times_ms: list[float] = []
        self.eval_log: list[tuple[str, int, float]] = []          # (as-of time, minutes received, milliseconds)
        self.alerts: list[dict] = []
        self.alert_log: dict[str, dict] = {}
        self.health: dict = {}
        self.started = time.time()
        self.as_of = None

    # -- stream input --------------------------------------------------------------------------------------------------------------------
    def feed_line(self, line: str) -> None:
        self._take(self.agg.feed_line(line))

    def feed(self, msg) -> None:
        self._take(self.agg.feed(msg))

    def _take(self, rows: list[dict]) -> None:
        for r in rows:
            if r["asset_id"] != self.asset_id:
                continue
            self.rows.append(r)
            self.since_eval += 1
            end = r["window_start_utc"] + pd.Timedelta(minutes=1)
            fine = self.fine_from is not None and end >= self.fine_from and (self.fine_to is None or end <= self.fine_to)
            if self.since_eval >= (self.fine_every if fine else self.every):
                self.evaluate()

    def finish(self) -> dict:
        self._take(self.agg.flush(self.asset_id))
        return self.evaluate(status="finished")

    # -- evaluation ----------------------------------------------------------------------------------------------------------------------
    def evaluate(self, status: str = "running") -> dict:
        self.since_eval = 0
        if not self.rows:
            return self._write(status)
        feat = rows_to_frame(self.rows)
        t0 = time.perf_counter()
        data = DevData(Path("."), self.assets, feat, pd.DataFrame(columns=["asset_id"]), pd.DataFrame(), pd.DataFrame())
        pred = self.method.predict(self.model, data, self.asset_id)
        self.as_of = feat["window_start_utc"].iloc[-1] + pd.Timedelta(minutes=1)
        self.alerts = to_contract(pred, self.assets, source=self.source, model_version=self.version) if len(pred) else []
        cleaned, report = clean_minutes(feat)
        self.health = data_health(cleaned, self.asset_row, hygiene=report)
        self.health["checks"] = check_ranges(cleaned, self.asset_row)
        self.times_ms.append((time.perf_counter() - t0) * 1000)
        self.eval_log.append((_iso(self.as_of), len(self.rows), self.times_ms[-1]))
        for a in self.alerts:
            if a["alert_id"] not in self.alert_log:
                lag = (self.as_of - pd.Timestamp(a["alert_time_utc"])).total_seconds() / 60
                self.alert_log[a["alert_id"]] = {"first_seen_as_of_utc": _iso(self.as_of), "published_minutes_after_alert_time": round(lag, 1)}
        return self._write(status)

    def latency(self) -> dict:
        t = np.asarray(self.times_ms) if self.times_ms else np.zeros(1)
        return {"evaluations": len(self.times_ms), "last_ms": round(float(t[-1]), 1), "p50_ms": round(float(np.percentile(t, 50)), 1),
                "p95_ms": round(float(np.percentile(t, 95)), 1), "max_ms": round(float(t.max()), 1),
                "note": "time to re-run the detector on all minutes received so far; grows with the length of the history"}

    def state(self, status: str) -> dict:
        s = {"asset_id": self.asset_id, "mode": "replay", "status": status, "model_version": self.version, "every_minutes": self.every,
             "as_of_utc": _iso(self.as_of) if self.as_of is not None else None, "minutes": int(len(self.rows)),
             "ingest": {k: int(v) for k, v in self.agg.stats.items()}, "latency": self.latency(), "health": self.health,
             "alerts": self.alerts, "alert_log": self.alert_log, "updated_wall_utc": _iso(pd.Timestamp.now(tz="UTC")),
             "started_wall_utc": _iso(pd.Timestamp(self.started, unit="s", tz="UTC"))}
        return json.loads(json.dumps(_scrub(s), default=_default))

    def _write(self, status: str) -> dict:
        s = self.state(status)
        if self.out is not None:
            self.out.mkdir(parents=True, exist_ok=True)
            tmp = self.out / "state.json.tmp"
            tmp.write_text(json.dumps(s, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            os.replace(tmp, self.out / "state.json")                       # readers never see a half-written file
        return s


def _default(o):
    return o.item() if isinstance(o, np.generic) else str(o)


def _scrub(x):
    """NaN and infinity are not JSON: they become null."""
    if isinstance(x, dict):
        return {k: _scrub(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_scrub(v) for v in x]
    if isinstance(x, (float, np.floating)) and not np.isfinite(x):
        return None
    return x


def replay_command(data_dir, asset, start=None, end=None, speed=0.0, limit=None) -> list[str]:
    cmd = [sys.executable, "-m", "retrofit_sim", "replay", "--data", str(data_dir), "--asset", asset, "--speed", str(speed)]
    for flag, v in (("--start", start), ("--end", end), ("--limit", limit)):
        if v is not None:
            cmd += [flag, str(v)]
    return cmd


def main(argv=None) -> int:
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser(description="Read-only live replay: messages in, alerts and data health out.")
    ap.add_argument("--asset", required=True)
    ap.add_argument("--data", default=None)
    ap.add_argument("--input", default=None, help="JSON Lines file with replay messages, or - for stdin. Without it the organizers' replay is started.")
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--speed", type=float, default=0.0, help="Replay speed factor, 0 = as fast as possible.")
    ap.add_argument("--every", type=int, default=15, help="Re-run the detector every N finished minutes.")
    ap.add_argument("--fine-from", default=None, help="From this data time on, re-run every --fine-every minutes (to measure alert delay with a long history).")
    ap.add_argument("--fine-to", default=None)
    ap.add_argument("--fine-every", type=int, default=1)
    ap.add_argument("--lateness", type=float, default=5.0, help="Seconds a minute stays open for late messages.")
    ap.add_argument("--model", default=str(ROOT / "models" / "wk.joblib"))
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "live"))
    ap.add_argument("--allow-test", action="store_true", help="Only for the frozen final prediction path. Never for demos or evaluation.")
    a = ap.parse_args(argv)

    data_dir = Path(a.data or default_data_dir())
    assets = pd.read_csv(data_dir / "assets.csv")
    if a.asset not in set(assets.asset_id):
        raise SystemExit(f"unknown asset {a.asset}")
    dev = set(assets[assets.split.isin(["train", "validation"])].asset_id)
    if a.asset not in dev and not a.allow_test:
        raise SystemExit(f"{a.asset} is a test pump: live replay is for the public pumps. (--allow-test exists for the frozen prediction path only.)")

    from ..diagnose import DiagnosisModel
    model_file = Path(a.model)
    model = DiagnosisModel.load(model_file)
    version = "wk-" + hashlib.sha256(model_file.read_bytes()).hexdigest()[:10]
    runner = LiveRunner(a.asset, assets, model, a.out, every=a.every, lateness_s=a.lateness, model_version=version, fine_from=a.fine_from, fine_every=a.fine_every, fine_to=a.fine_to)

    proc = None
    if a.input in (None, "-"):
        if a.input is None:
            proc = subprocess.Popen(replay_command(data_dir, a.asset, a.start, a.end, a.speed, a.limit), stdout=subprocess.PIPE, text=True, bufsize=1)
            stream = proc.stdout
        else:
            stream = sys.stdin
    else:
        stream = open(a.input, encoding="utf-8")
    t0 = time.perf_counter()
    try:
        for line in stream:
            runner.feed_line(line)
    finally:
        if proc is not None:
            proc.stdout.close()
            proc.wait()
    s = runner.finish()
    lat = s["latency"]
    print(f"{a.asset}: {s['minutes']} minutes, {len(s['alerts'])} alerts, health {s['health'].get('status')}, {lat['evaluations']} evaluations "
          f"(median {lat['p50_ms']} ms, worst {lat['max_ms']} ms), {time.perf_counter() - t0:.1f} s in total -> {runner.out / 'state.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
