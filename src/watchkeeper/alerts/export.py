"""Turn prediction rows (organizer CSV format) into contract alerts (docs/alert.schema.json) and write them per asset."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

# Channels that change what we can conclude. Missing ones are reported as uncertainty.
CORE_CHANNELS = ["suction_pressure_kpa", "flow_m3_h", "vibration_rms_mm_s", "bearing_temp_c", "motor_winding_temp_c"]

_Z = re.compile(r"^(?P<ch>[a-z0-9_]+) z=(?P<z>[+-]?\d+(?:\.\d+)?)$")
_ALONE = re.compile(r"^(?P<ch>[a-z0-9_]+) deviates alone \(z=(?P<z>[+-]?\d+(?:\.\d+)?)\)$")
_NPSH = re.compile(r"^npsh_margin=(?P<v>[0-9.]+)$")
_FROZEN = re.compile(r"^(?P<ch>[a-z0-9_]+) frozen$")


def parse_evidence(text: str) -> list[dict]:
    """Split a free-text evidence string such as 'B1 mode-aware z: motor_speed_rpm z=+6.2, ...' into structured items."""
    body = text.split(": ", 1)[1] if isinstance(text, str) and ": " in text else (text if isinstance(text, str) else "")
    items = []
    for token in [t.strip() for t in body.split(", ") if t.strip()]:
        if m := _ALONE.match(token):
            z = float(m["z"])
            items.append({"channel": m["ch"], "text": f"deviates alone by {z:+.1f} robust standard deviations; related channels did not follow", "z": z})
        elif m := _Z.match(token):
            z = float(m["z"])
            items.append({"channel": m["ch"], "text": f"{z:+.1f} robust standard deviations from the baseline for this operating regime", "z": z})
        elif m := _NPSH.match(token):
            items.append({"channel": "npsh_margin (estimated)", "text": f"estimated NPSH margin {float(m['v']):.2f}; cavitation starts below about 1.15", "z": None})
        elif m := _FROZEN.match(token):
            items.append({"channel": m["ch"], "text": "constant value while the pump runs", "z": None})
        elif token == "missing rows":
            items.append({"channel": "GATEWAY", "text": "telemetry rows are missing", "z": None})
        else:
            items.append({"channel": "n/a", "text": token, "z": None})
    return items


def _sensor_check(event_class: str, fault_type: str, evidence: list[dict]) -> dict:
    if event_class == "SENSOR":
        reasons = {
            "COMMUNICATION_LOSS": "all channels stopped together, which points at the gateway",
            "SENSOR_STUCK": "the value stayed constant while the pump was running",
        }
        return {"verdict": "sensor", "reason": reasons.get(fault_type, "one instrument moved while the channels coupled to it did not")}
    if fault_type == "UNKNOWN":
        return {"verdict": "unclear", "reason": "the pattern does not match a known machine or instrument fault"}
    channels = {e["channel"] for e in evidence if e["channel"] != "n/a"}
    if any(c.startswith("npsh_margin") for c in channels):
        return {"verdict": "machine", "reason": "calculated from suction pressure, fluid temperature and the pump data sheet, not read from one instrument"}
    if len(channels) >= 2:
        return {"verdict": "machine", "reason": "several related channels deviated together"}
    return {"verdict": "machine", "reason": "one channel deviated; coupled channels were not available to confirm"}


def _alternatives(row, confidence: float) -> list[dict]:
    """Next-best fault types from the model, rescaled so that together with the main diagnosis they add up to at most one."""
    raw = getattr(row, "alternatives", None)
    alts = json.loads(raw) if isinstance(raw, str) and raw else []
    total = sum(a["p"] for a in alts)
    return [{"fault_type": a["fault_type"], "p": round(a["p"] / total * (1.0 - confidence), 3)} for a in alts] if total > 0 else []


def to_contract(pred: pd.DataFrame, assets: pd.DataFrame, source: str) -> list[dict]:
    """One contract alert per prediction row, sorted by asset and time."""
    channels = {r.asset_id: set(str(r.channels_available).split("|")) for r in assets.itertuples()}
    alerts, seen = [], {}
    for r in pred.sort_values(["asset_id", "alert_time_utc"], kind="stable").itertuples():
        evidence = parse_evidence(getattr(r, "evidence", ""))
        t = pd.Timestamp(r.alert_time_utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        base = f"{r.asset_id}-{t}"
        seen[base] = seen.get(base, 0) + 1
        alerts.append({
            "alert_id": base if seen[base] == 1 else f"{base}-{seen[base]}",
            "asset_id": r.asset_id,
            "alert_time_utc": t,
            "event_class": r.event_class,
            "fault_type": r.fault_type,
            "confidence": float(min(max(r.confidence, 0.0), 1.0)),
            "alternatives": _alternatives(r, float(min(max(r.confidence, 0.0), 1.0))),
            "evidence": evidence,
            "sensor_check": _sensor_check(r.event_class, r.fault_type, evidence),
            "uncertainty": {
                "missing_channels": [c for c in CORE_CHANNELS if c not in channels.get(r.asset_id, set())],
                "data_quality": "poor" if r.fault_type == "COMMUNICATION_LOSS" else "ok",
            },
            "recommended_action": getattr(r, "recommended_action", None) or "Inspect the pump.",
            "requires_human_approval": True,
            "what_if": None,
            "source": source,
        })
    return alerts


def write_predictions_csv(pred: pd.DataFrame, path) -> Path:
    """Write the organizers' submission CSV (asset_id, alert_time_utc, event_class, fault_type, confidence, evidence, recommended_action)."""
    cols = ["asset_id", "alert_time_utc", "event_class", "fault_type", "confidence", "evidence", "recommended_action"]
    out = pred.reindex(columns=cols).copy()
    out["confidence"] = out["confidence"].astype(float).round(3)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.sort_values(["asset_id", "alert_time_utc"], kind="stable").to_csv(path, index=False)
    return path


def write_alerts(alerts: list[dict], out_dir, asset_ids=None) -> list[Path]:
    """Write artifacts/alerts/<asset_id>.json (an empty list for an asset without alerts)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    by_asset = {a: [] for a in (asset_ids or [])}
    for al in alerts:
        by_asset.setdefault(al["asset_id"], []).append(al)
    paths = []
    for asset, items in sorted(by_asset.items()):
        p = out / f"{asset}.json"
        p.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        paths.append(p)
    return paths
