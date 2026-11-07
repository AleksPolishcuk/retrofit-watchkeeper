#!/usr/bin/env python3
"""Threshold scan for the signature detectors without running the whole pipeline: false episodes on healthy fleets against hits and delay on faulty ones.

  .venv/bin/python eval/probes/signature_scan.py
Healthy side: healthy_train fleets (no faults, every episode is false). Event side: tune fleets and the 9 dev pumps. Hold fleets and test pumps are never read.
An episode is a run of flagged minutes lasting at least `persist` minutes (fused) or at least one minute (slow), separated from the previous one by 12 h.
"""
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from watchkeeper import methods as M  # noqa: E402
from watchkeeper.bank import load_set  # noqa: E402
from watchkeeper.detect.signature import fused_type, signature_scores, slow_detect  # noqa: E402
from watchkeeper.evalkit import load_dev  # noqa: E402

PERSIST = 12


def episodes(flag: np.ndarray, t: pd.Series, persist: int) -> list[int]:
    """Indices at which a run of `persist` consecutive flagged minutes completes, at most one per 12 h."""
    out, run, last = [], 0, None
    for j, f in enumerate(flag):
        run = run + 1 if f else 0
        if run == persist and (last is None or t.iloc[j] - last > pd.Timedelta(hours=12)):
            out.append(j)
            last = t.iloc[j]
    return out


def per_asset(d, drop=()):
    zf = M._zf(d, True, 60, 6, drop)
    for a in d.ids:
        g = zf[zf.asset_id == a].reset_index(drop=True)
        yield a, g, pd.to_datetime(g["window_start_utc"], utc=True)


def scan(name, d, detectors, drop=()):
    ev = d.events.copy()
    for c in ("onset_utc", "detectable_utc", "end_utc"):
        ev[c] = pd.to_datetime(ev[c], utc=True, format="ISO8601") if c in ev else pd.NaT
    ev = ev[ev["observable"].astype(str).str.lower().isin(["true", "1"]) & ev["detectable_utc"].notna()] if len(ev) else ev
    rows = []
    cache = {}
    for a, g, t in per_asset(d, drop):
        cache[a] = (g, t, signature_scores(g, 15), fused_type(g, 15))
    days = sum((t.max() - t.min()).total_seconds() / 86400 + 1 / 1440 for _, _, t in per_asset(d, drop))
    for label, fn in detectors:
        n_ep, hits, delays, type_ok = 0, 0, [], 0
        for a, (g, t, sc, ft) in cache.items():
            flag, kind = fn(g, sc, ft)
            persist = PERSIST if label.startswith("fused") else 1
            idx = episodes(flag, t, persist)
            n_ep += len(idx)
            for e in ev[ev.asset_id == a].itertuples():
                end = e.end_utc if pd.notna(e.end_utc) else t.max() + pd.Timedelta(minutes=1)
                inside = [j for j in idx if e.onset_utc <= t.iloc[j] <= end]
                # an episode that began before the event but is still running when it starts also counts: use the first flagged minute inside the event
                if not inside:
                    mask = ((t >= e.onset_utc) & (t <= end)).to_numpy() & flag
                    if mask.any() and flag[np.flatnonzero(mask)[0] - 1 if np.flatnonzero(mask)[0] else 0]:
                        inside = [int(np.flatnonzero(mask)[0])]
                if inside:
                    j = inside[0]
                    hits += 1
                    delays.append((t.iloc[j] - e.detectable_utc).total_seconds() / 3600)
                    type_ok += int(kind[j] == e.fault_type)
        rows.append({"detector": label, "set": name, "episodes": n_ep, "per pump-month": round(30 * n_ep / days, 2), "events": len(ev), "hit": hits,
                     "median delay h": None if not delays else round(float(np.median(delays)), 1), "type ok": type_ok})
    return rows


def main() -> int:
    detectors = []
    for h in (5, 6, 7, 8, 10, 12):
        detectors.append((f"fused h={h}", lambda g, sc, ft, h=h: ((sc.to_numpy() >= h).any(axis=1) if not sc.empty else np.zeros(len(g), bool), ft.to_numpy())))
    for h in (6, 8, 12, 16, 24):
        for k in (0.5, 1.0):
            detectors.append((f"slow h={h} k={k}", lambda g, sc, ft, h=h, k=k: slow_detect(g, h, k)))
    out = []
    for name, d in (("healthy_train", load_set("healthy_train")), ("tune", load_set("tune")), ("dev9", load_dev())):
        out += scan(name, d, detectors)
        print(pd.DataFrame(out[-len(detectors):]).to_string(index=False, header=name == "healthy_train"), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
