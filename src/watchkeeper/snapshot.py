"""A static snapshot of the read-only API, so the interface can be hosted without a Python server (for example on Vercel).

The API only ever reads recorded data, so every answer it gives for the recorded pumps can be written to a file once. This module calls the real API
routes in process and saves each answer under a predictable name; the interface asks for the same names (web/src/snapshot.ts) when it is built with
VITE_SNAPSHOT=1. The names are fixed by `snapshot_path` and checked against web/tests/snapshot-cases.json from both languages.

What the snapshot does not contain: telemetry of the test pumps (the API does not serve it), the live replay (it needs a running process) and the
review log (it lives in the browser).

  python -m watchkeeper.snapshot --out web/public/snapshot
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from .api.app import CHANNELS, create_app
from .evalkit import ROOT, default_data_dir

STEPS = (10, 60, 120)                                                   # the minute steps the interface asks for (case view, whole week, overview)
ATTRIBUTION = 'RETROFIT AI 2026 synthetic pump benchmark, Since AI Hackathon 2026 (CC BY 4.0)'


def safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "-", text)


def snapshot_path(url: str) -> str | None:
    """File name (relative to the snapshot folder) of the answer to this API URL, or None when the route is not part of the snapshot."""
    u = urlsplit(url)
    q = dict(parse_qsl(u.query))
    p = u.path.rstrip("/")
    if p == "/api/assets":
        return "assets.json"
    if p == "/api/results":
        return "results.json"
    if p == "/api/health":
        return "health.json"
    if p == "/api/alerts":
        return f"alerts/{safe(q['asset_id'])}.json" if q.get("asset_id") else "alerts.json"
    if p == "/api/alerts/archive":
        return f"archive/{safe(q.get('asset_id', 'all'))}.json"
    if p == "/api/timeline" and q.get("asset_id"):
        return f"timeline/{safe(q['asset_id'])}.json"
    if p == "/api/series" and {"asset_id", "channel", "step_min"} <= q.keys():
        return f"series/{safe(q['asset_id'])}__{safe(q['channel'])}__{safe(q['step_min'])}.json"
    if p == "/api/data-health" and q.get("asset_id"):
        return f"data-health/{safe(q['asset_id'])}.json" if not q.get("as_of") else f"data-health/{safe(q['asset_id'])}__{safe(q['as_of'])}.json"
    if p == "/api/whatif" and {"asset_id", "time_utc", "fault_type"} <= q.keys():
        return f"whatif/{safe(q['asset_id'])}__{safe(q['time_utc'])}__{safe(q['fault_type'])}.json"
    return None


def export_snapshot(out, data_dir=None, alerts_dir=None, archive_dir=None, assets: list[str] | None = None, steps=STEPS, whatif: bool = True) -> dict:
    """Write the snapshot to `out`. `assets` limits the pumps (default all twelve); `whatif=False` skips the simulator calls."""
    from fastapi.testclient import TestClient
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    empty_live = Path(tempfile.mkdtemp(prefix="wk-no-live-"))
    app = create_app(data_dir or default_data_dir(), alerts_dir=alerts_dir or ROOT / "artifacts" / "alerts", live_dir=empty_live,
                     archive_dir=archive_dir or ROOT / "artifacts" / "alerts_archive")
    c = TestClient(app)
    written: dict[str, int] = {}
    skipped: list[str] = []

    def save(url: str) -> dict | list | None:
        rel = snapshot_path(url)
        r = c.get(url)
        if rel is None or r.status_code != 200:
            skipped.append(f"{url} -> {r.status_code}")
            return None
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(r.text, encoding="utf-8")
        written[rel] = len(r.content)
        return r.json()

    all_assets = save("/api/assets") or []
    save("/api/health")
    save("/api/results")
    alerts = (save("/api/alerts") or {}).get("alerts", [])
    for a in all_assets:
        pid = a["asset_id"]
        if assets and pid not in assets:
            continue
        save(f"/api/alerts?asset_id={pid}")
        save(f"/api/alerts/archive?asset_id={pid}")
        save(f"/api/timeline?asset_id={pid}")
        mine = [x for x in alerts if x["asset_id"] == pid]
        if a["telemetry_served"]:
            for ch in a["channels_available"]:
                if ch in CHANNELS:
                    for st in steps:
                        save(f"/api/series?asset_id={pid}&channel={ch}&step_min={st}")
            save(f"/api/data-health?asset_id={pid}")
            for x in mine:
                save(f"/api/data-health?asset_id={pid}&as_of={x['alert_time_utc']}")
        if whatif:
            for x in mine:                                                  # the interface asks for any alert; the API answers "not available" for the rest
                save(f"/api/whatif?asset_id={pid}&time_utc={x['alert_time_utc']}&fault_type={x['fault_type']}")
    served = {a["asset_id"] for a in all_assets if a["telemetry_served"]}
    leaked = [rel for rel in written if rel.startswith(("series/", "data-health/")) and rel.split("/")[1].split("__")[0].split(".json")[0] not in served]
    if leaked:
        raise SystemExit(f"refusing to write telemetry of pumps that are not served: {leaked[:3]}")
    manifest = {"created_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "files": len(written), "bytes": sum(written.values()),
                "attribution": ATTRIBUTION, "note": "Static snapshot of the read-only API for the recorded simulated pumps. No telemetry of the test pumps, no live replay.",
                "skipped": skipped}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "web" / "public" / "snapshot"))
    ap.add_argument("--no-whatif", action="store_true", help="skip the simulator calls")
    a = ap.parse_args(argv)
    m = export_snapshot(a.out, whatif=not a.no_whatif)
    print(f"{m['files']} files, {m['bytes'] / 1e6:.1f} MB -> {a.out}" + (f" ({len(m['skipped'])} answers were not 200 and were skipped)" if m["skipped"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
