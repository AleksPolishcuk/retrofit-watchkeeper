"""Append-only snapshots of the alerts of each model version.

`write_alerts` overwrites `artifacts/alerts/<asset>.json` whenever the engine is re-run, so a re-run with a new model would erase what an operator was
shown before (enterprise scenarios A17 and P27). This keeps one immutable file per model version and pump, and an index of what was written when.
Nothing here is read by the detector; it only lets a person look back.

  python -m watchkeeper.alerts.archive                 # archive artifacts/alerts as they are, grouped by the model_version inside each alert
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

DEFAULT_SOURCE = Path(__file__).resolve().parents[3] / "artifacts" / "alerts"
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "artifacts" / "alerts_archive"
INDEX = "index.jsonl"


def _digest(alerts: list[dict]) -> str:
    return hashlib.sha256(json.dumps(alerts, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name) or "unversioned"


def read_index(root=DEFAULT_ROOT, asset_id: str | None = None) -> list[dict]:
    f = Path(root) / INDEX
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if asset_id is None or e.get("asset_id") == asset_id:
            out.append(e)
    return out


def archive_alerts(alerts: list[dict], root=DEFAULT_ROOT, written_utc: str | None = None) -> list[dict]:
    """Keep a snapshot of these alerts per (model version, pump). Returns the index entries that were new; an identical snapshot is not written twice.

    A snapshot is never overwritten. If a version already has a different snapshot for a pump, the new one gets a timestamp in its file name.
    """
    root = Path(root)
    stamp = written_utc or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    groups: dict[tuple[str, str], list[dict]] = {}
    for a in alerts:
        groups.setdefault((a.get("model_version") or "unversioned", a["asset_id"]), []).append(a)
    known = {(e["model_version"], e["asset_id"], e["sha256"]) for e in read_index(root)}
    written = []
    for (version, asset), items in sorted(groups.items()):
        items = sorted(items, key=lambda x: x["alert_time_utc"])
        digest = _digest(items)
        if (version, asset, digest) in known:
            continue
        folder = root / _safe(version)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{asset}.json"
        if target.exists():
            target = folder / f"{asset}.{stamp.replace(':', '')}.json"
            n = 1
            while target.exists():
                n += 1
                target = folder / f"{asset}.{stamp.replace(':', '')}-{n}.json"
        target.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        entry = {"written_utc": stamp, "model_version": version, "asset_id": asset, "alerts": len(items), "sha256": digest, "file": str(target.relative_to(root))}
        with open(root / INDEX, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        written.append(entry)
    return written


def archive_dir(src=DEFAULT_SOURCE, root=DEFAULT_ROOT) -> list[dict]:
    """Archive every `<asset>.json` in a directory of contract alerts."""
    alerts: list[dict] = []
    for f in sorted(Path(src).glob("*.json")):
        try:
            items = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        alerts += [a for a in items if isinstance(a, dict) and "asset_id" in a and "alert_time_utc" in a]
    return archive_alerts(alerts, root)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from", dest="src", default=str(DEFAULT_SOURCE))
    ap.add_argument("--out", default=str(DEFAULT_ROOT))
    a = ap.parse_args(argv)
    new = archive_dir(a.src, a.out)
    print(f"{len(new)} new snapshot(s) in {a.out}" + "".join(f"\n  {e['model_version']} {e['asset_id']} ({e['alerts']} alerts)" for e in new))
    return 0


if __name__ == "__main__":
    sys.exit(main())
