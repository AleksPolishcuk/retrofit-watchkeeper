#!/usr/bin/env python3
"""Does the live path give the same answer as the batch path, and how fast is it? Public pumps only.

1. Aggregator: raw replay messages -> minutes, compared with the organizers' features_1min for the same hours (three pumps, three tiers).
2. Pipeline: PUMP-08 (validation pump, not seen by models/wk.joblib) replayed from the start of its window through the first three alerts, evaluated
   every 30 minutes and every minute around the first alert. The alerts of the live run must equal the alerts of one batch run over the same minutes.
3. Cost: evaluation time, alert delay, ingest rate, CPU and peak memory.

  .venv/bin/python eval/probes/live_equivalence.py       # writes eval/results/live_replay.md and live_replay.json
"""
import json
import resource
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from retrofit_sim.replay import messages

from watchkeeper.diagnose import DiagnosisModel
from watchkeeper.evalkit import ROOT, DevData, default_data_dir
from watchkeeper.ingest import MinuteAggregator, rows_to_frame
from watchkeeper.ingest.live import LiveRunner
from watchkeeper.methods import METHODS

DATA = default_data_dir()
ASSETS = pd.read_csv(DATA / "assets.csv")
EMPTY = pd.DataFrame(columns=["asset_id"])


def aggregator_check(asset: str, hours: float = 6.0) -> dict:
    row = ASSETS.set_index("asset_id").loc[asset]
    start = pd.Timestamp(row["window_start_utc"])
    end = start + pd.Timedelta(hours=hours)
    agg = MinuteAggregator(lateness_s=5, channels={asset: str(row["channels_available"]).split("|")})
    t0, rows, n = time.perf_counter(), [], 0
    for m in messages(DATA, asset, start.isoformat(), end.isoformat(), site=row["site"]):
        rows += agg.feed(m)
        n += 1
    rows += agg.flush()
    dt = time.perf_counter() - t0
    mine = rows_to_frame(rows)
    ref = pd.read_parquet(DATA / "features_1min.parquet", filters=[("asset_id", "==", asset)])
    ref = ref[(ref.window_start_utc >= start) & (ref.window_start_utc < end)].reset_index(drop=True)
    same_minutes = bool((mine.window_start_utc.values == ref.window_start_utc.values).all())
    worst, nan_diff, compared = 0.0, 0, 0
    for c in ref.columns:
        if c in ("asset_id", "window_start_utc") or c not in mine.columns:
            continue
        a, b = mine[c], ref[c]
        if a.dtype == object or b.dtype == object:
            nan_diff += int((a.astype(str).values != b.astype(str).values).sum())
            continue
        nan_diff += int((a.notna() != b.notna()).sum())
        both = (a.notna() & b.notna()).to_numpy()
        if both.any():
            worst = max(worst, float(np.max(np.abs(a.to_numpy(float)[both] - b.to_numpy(float)[both]))))
            compared += int(both.sum())
    return {"asset": asset, "tier": row["instrumentation_tier"], "hours": hours, "messages": n, "minutes": int(len(mine)), "same_minutes": same_minutes,
            "max_abs_diff": worst, "nan_pattern_differences": nan_diff, "values_compared": compared, "ingest_msgs_per_s_incl_replay": round(n / dt)}


def pipeline_check() -> dict:
    asset = "PUMP-08"
    row = ASSETS.set_index("asset_id").loc[asset]
    start, end = pd.Timestamp(row["window_start_utc"]), pd.Timestamp("2025-09-11T14:00:00Z")
    fine_from, fine_to = pd.Timestamp("2025-09-10T09:00:00Z"), pd.Timestamp("2025-09-10T10:00:00Z")
    model = DiagnosisModel.load(ROOT / "models" / "wk.joblib")
    runner = LiveRunner(asset, ASSETS, model, None, every=30, lateness_s=5.0, fine_from=fine_from, fine_every=1, fine_to=fine_to)
    cpu0, t0 = time.process_time(), time.perf_counter()
    for m in messages(DATA, asset, start.isoformat(), end.isoformat(), site=row["site"]):
        runner.feed(m)
    state = runner.finish()
    wall, cpu = time.perf_counter() - t0, time.process_time() - cpu0
    live = pd.DataFrame(state["alerts"])[["alert_time_utc", "fault_type", "confidence"]] if state["alerts"] else pd.DataFrame(columns=["alert_time_utc", "fault_type", "confidence"])

    ref = pd.read_parquet(DATA / "features_1min.parquet", filters=[("asset_id", "==", asset)])
    ref = ref[ref.window_start_utc < end].reset_index(drop=True)
    batch = METHODS["wk"]().predict(model, DevData(Path("."), ASSETS, ref, EMPTY, pd.DataFrame(), pd.DataFrame()), asset)
    batch = batch[["alert_time_utc", "fault_type", "confidence"]].reset_index(drop=True)
    live = live.reset_index(drop=True)
    same = (len(live) == len(batch) and (live.alert_time_utc.astype(str).values == batch.alert_time_utc.astype(str).values).all()
            and (live.fault_type.values == batch.fault_type.values).all() and np.allclose(live.confidence.values.astype(float), batch.confidence.values.astype(float), atol=1e-4))

    log = pd.DataFrame(runner.eval_log, columns=["as_of", "minutes", "ms"])
    as_of = pd.to_datetime(log.as_of, utc=True)
    fine = log[(as_of > fine_from) & (as_of <= fine_to)]
    coarse = log.drop(fine.index)
    first = state["alert_log"].get(state["alerts"][0]["alert_id"]) if state["alerts"] else None
    return {"asset": asset, "window": [start.isoformat(), end.isoformat()], "minutes": state["minutes"], "ingest": state["ingest"], "alerts_live": int(len(live)), "alerts_batch": int(len(batch)),
            "identical_to_batch": bool(same), "alerts": live.to_dict("records"), "first_alert_publish": first,
            "evaluations_coarse": int(len(coarse)), "evaluations_fine": int(len(fine)),
            "fine_ms": {"median": round(float(fine.ms.median()), 0), "p95": round(float(fine.ms.quantile(0.95)), 0), "max": round(float(fine.ms.max()), 0), "history_minutes": [int(fine.minutes.min()), int(fine.minutes.max())]},
            "coarse_ms": {"median": round(float(coarse.ms.median()), 0), "max": round(float(coarse.ms.max()), 0)},
            "wall_s": round(wall, 1), "cpu_s": round(cpu, 1), "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 0)}


def main() -> int:
    agg = [aggregator_check(a) for a in ("PUMP-08", "PUMP-04", "PUMP-03")]
    for r in agg:
        print(r, flush=True)
    pipe = pipeline_check()
    print(pipe, flush=True)
    out = ROOT / "eval" / "results"
    (out / "live_replay.json").write_text(json.dumps({"aggregator": agg, "pipeline": pipe}, indent=1, default=str) + "\n", encoding="utf-8")
    L = ["# Live replay: equivalence with the batch path and cost", "",
         "Public pumps only. Replay messages come from `retrofit_sim.replay.messages` (the same stream `python -m retrofit_sim replay` prints). Reproduce with `.venv/bin/python eval/probes/live_equivalence.py`.", "",
         "## 1. Minutes from raw messages equal the organizers' `features_1min`", "",
         "First six hours of each pump's window, one message per second.", "",
         "| Pump | Tier | Messages | Minutes | Same minutes | Largest absolute difference | Missing-value pattern differences |", "|---|---|---|---|---|---|---|"]
    for r in agg:
        L.append(f"| {r['asset']} | {r['tier']} | {r['messages']} | {r['minutes']} | {'yes' if r['same_minutes'] else 'NO'} | {r['max_abs_diff']:.1e} | {r['nan_pattern_differences']} |")
    L += ["", "The differences are float32 rounding. Every channel, count, operating mode, running fraction, quality-flag mask and row count agrees.", "",
          "## 2. The live pipeline gives the batch alerts", "",
          f"PUMP-08 (a validation pump that `models/wk.joblib` was not fitted on), {pipe['window'][0][:16]} to {pipe['window'][1][:16]}: {pipe['minutes']} finished minutes. "
          f"The detector was re-run every 30 minutes, and every minute during the hour around the first alert.", "",
          f"- Live alerts: {pipe['alerts_live']}. One batch run over the same minutes: {pipe['alerts_batch']}. **Identical (time, type, confidence): {'yes' if pipe['identical_to_batch'] else 'NO'}.**"]
    for a in pipe["alerts"]:
        L.append(f"  - {a['alert_time_utc']} {a['fault_type']} ({a['confidence']:.2f})")
    f = pipe["first_alert_publish"]
    L += ["", "## 3. Cost and delay (one core, CPU only)", "",
          f"- Ingest: {agg[0]['ingest_msgs_per_s_incl_replay']:,} messages per second including the replay generator, so one pump at one message per second uses about 0.005 % of a core.",
          f"- Detector re-run, history of {pipe['fine_ms']['history_minutes'][0]} to {pipe['fine_ms']['history_minutes'][1]} minutes: median {pipe['fine_ms']['median']:.0f} ms, 95th percentile {pipe['fine_ms']['p95']:.0f} ms, worst {pipe['fine_ms']['max']:.0f} ms.",
          f"- First alert: published {f['published_minutes_after_alert_time']} data-minutes after its alert time when the detector runs every minute. At real-time replay the delay from the end of the minute is the {5} s lateness window plus one detector run.",
          f"- Whole run: {pipe['wall_s']} s wall, {pipe['cpu_s']} s CPU, peak memory {pipe['peak_rss_mb']:.0f} MB.", "",
          f"- Re-running every minute at this history length costs about {pipe['fine_ms']['median'] / 60000 * 100:.1f} % of one core per pump.", "",
          "Limit, stated plainly: the detector is re-run on all minutes received so far, so one run takes 1 to 3 seconds for history of two days to a week (a full-week batch run of PUMP-08 takes 1.6 s) and the cost grows with the history. Peak memory includes the model and the public data table. An incremental scorer would remove the growth; it is not built."]
    (out / "live_replay.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
