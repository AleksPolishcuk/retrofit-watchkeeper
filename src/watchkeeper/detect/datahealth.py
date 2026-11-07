"""Data health: can this pump be evaluated right now, and if not, why not.

The detector is silent when data are bad. A silent detector looks like a healthy pump, which is the most dangerous mistake an operator-assist layer can make
(scenarios A02, A03, A04, A09, A13 and A18 of the enterprise verification, P02, P03 and P10 of the pilot matrix). This module reads the minute features of one
pump, up to a chosen moment, and states what is missing in plain words. It only reads. It does not change any alert.

Status, most severe first:
  NO_DATA             nothing received for more than 15 minutes
  INSUFFICIENT_DATA   rows arrive but no physical channel has fresh values
  DEGRADED            some expected channel is stale or missing, the gateway was silent, the speed signal is lost, or many readings carry quality flags
  BASELINE_LEARNING   fewer than 120 running minutes seen: the pump's normal is not yet known
  OK
"""
from __future__ import annotations

import pandas as pd

NAMES = {
    "motor_speed_rpm": "Speed", "motor_current_a": "Motor current", "motor_power_kw": "Motor power", "suction_pressure_kpa": "Suction pressure",
    "discharge_pressure_kpa": "Discharge pressure", "flow_m3_h": "Flow", "fluid_temp_c": "Fluid temperature", "bearing_temp_c": "Bearing temperature",
    "motor_winding_temp_c": "Winding temperature", "vibration_rms_mm_s": "Vibration", "vibration_accel_rms_g": "Vibration (acceleration)",
    "vibration_crest_factor": "Vibration (crest factor)", "valve_position_pct": "Valve position", "ambient_temp_c": "Ambient temperature",
}
SPARSE = {"vibration_rms_mm_s", "vibration_accel_rms_g", "vibration_crest_factor", "bearing_temp_c"}      # wireless sensors on retrofit pumps report every few minutes
CONTEXT_ONLY = {"ambient_temp_c"}                                                                         # does not describe the pump itself
QUALITY_BITS = {1: "COMM_LOSS", 2: "OUT_OF_RANGE", 4: "STALE", 8: "BAD_SENSOR_STATUS", 16: "STARTUP_INHIBIT"}
NO_DATA_MIN = 15
STALE_MIN = 15
STALE_SPARSE_MIN = 25
MISSING_MIN = 120
BASELINE_MIN = 120
STARTUP_MIN = 10


def _t(ts) -> str:
    return pd.Timestamp(ts).strftime("%d %b %H:%M")


def _channels(asset) -> list[str]:
    raw = asset.get("channels_available", "") if hasattr(asset, "get") else ""
    return [c for c in str(raw).split("|") if c]


def data_health(feat: pd.DataFrame, asset, as_of=None, hygiene: dict | None = None) -> dict:
    """Health of one pump from its minute features, using only rows up to `as_of` (default: all rows). `asset` is a row of assets.csv."""
    f = feat.copy()
    f["_t"] = pd.to_datetime(f["window_start_utc"], utc=True)
    f = f.sort_values("_t")
    cut = None
    if as_of is not None:
        cut = pd.Timestamp(as_of)
        cut = cut.tz_localize("UTC") if cut.tzinfo is None else cut.tz_convert("UTC")
        f = f[f["_t"] <= cut]
    out = {"status": "NO_DATA", "reasons": [], "as_of": None, "last_data_utc": None, "minutes_since_last_data": None, "mode": None,
           "channels": [], "gaps": [], "quality": {"flagged_last_60": 0, "flagged_total": 0, "bits": {}}, "baseline_running_minutes": 0, "hygiene": hygiene}
    if f.empty:
        out["reasons"] = ["No data received for this pump."]
        return out
    last = f["_t"].iloc[-1]
    now = cut if cut is not None else last + pd.Timedelta(minutes=1)
    silent = (now - last).total_seconds() / 60
    out.update(as_of=now.strftime("%Y-%m-%dT%H:%M:%SZ"), last_data_utc=last.strftime("%Y-%m-%dT%H:%M:%SZ"), minutes_since_last_data=round(max(silent - 1, 0), 1), mode=str(f["operating_mode"].iloc[-1]) if "operating_mode" in f else None)

    reasons: list[str] = []
    severity = 0                      # 1 baseline learning, 2 degraded, 3 insufficient, 4 no data

    # 1. gateway silence: gaps between consecutive rows
    dt = f["_t"].diff().dt.total_seconds().div(60)
    gap_rows = f[dt > 3]
    for idx in gap_rows.index[-5:]:
        end = f.loc[idx, "_t"]
        missing = int(dt.loc[idx]) - 1
        out["gaps"].append({"start_utc": (end - pd.Timedelta(minutes=missing + 1)).strftime("%Y-%m-%dT%H:%M:%SZ"), "end_utc": end.strftime("%Y-%m-%dT%H:%M:%SZ"), "minutes": missing})
    recent_gaps = [g for g in out["gaps"] if pd.Timestamp(g["end_utc"]) > now - pd.Timedelta(minutes=60)]
    if recent_gaps:
        g = recent_gaps[-1]
        reasons.append(f"Gateway was silent for {g['minutes']} minutes ({_t(g['start_utc'])} to {_t(g['end_utc'])}); the state of the pump in between is unknown.")
        severity = max(severity, 2)

    if silent - 1 > NO_DATA_MIN:
        out["status"] = "NO_DATA"
        out["reasons"] = [f"No data for {int(silent - 1)} minutes (last row {_t(last)})."] + reasons
        return out

    # 2. channels
    expected = _channels(asset)
    live = 0
    for name in expected:
        col = f"{name}__count"
        sparse = name in SPARSE and float(asset.get("wireless_update_s", 0) or 0) > 60 if hasattr(asset, "get") else False
        if col not in f:
            continue
        seen = f.loc[f[col].fillna(0) > 0, "_t"]
        age = (now - seen.iloc[-1]).total_seconds() / 60 if len(seen) else None
        stale_after = STALE_SPARSE_MIN if sparse else STALE_MIN
        if age is None or age > MISSING_MIN:
            st = "missing"
        elif age > stale_after:
            st = "stale"
        else:
            st = "live"
        if st == "live" and name not in CONTEXT_ONLY:
            live += 1
        out["channels"].append({"name": name, "label": NAMES.get(name, name), "status": st, "last_seen_utc": seen.iloc[-1].strftime("%Y-%m-%dT%H:%M:%SZ") if len(seen) else None, "age_minutes": None if age is None else round(age, 1)})
        if st != "live" and name not in CONTEXT_ONLY:
            when = f"nothing received since {_t(seen.iloc[-1])} ({int(age)} min)" if len(seen) else "nothing received in this window"
            tail = " Operating-point checks are suspended." if name == "motor_speed_rpm" else ""
            reasons.append(f"{NAMES.get(name, name)}: {when}.{tail}")
            severity = max(severity, 2)
    physical = [c for c in out["channels"] if c["name"] not in CONTEXT_ONLY]
    if physical and live == 0:
        reasons.insert(0, "Rows arrive but every measurement is missing or stale: nothing can be evaluated.")
        severity = max(severity, 3)

    # 3. operating mode and how much of the pump's normal has been seen
    run = (f["operating_mode"] == "RUNNING") & (f["running_fraction"].fillna(1.0) >= 0.99) if "operating_mode" in f else pd.Series(True, index=f.index)
    out["baseline_running_minutes"] = int(run.sum())
    if "operating_mode" in f and f["operating_mode"].iloc[-1] == "RUNNING":
        tail_run = 0
        for v in run.to_numpy()[::-1]:
            if not v:
                break
            tail_run += 1
        if tail_run < STARTUP_MIN and len(f) > tail_run:
            reasons.append(f"Pump started {tail_run} minutes ago: checks begin {STARTUP_MIN} minutes after a start.")
    if out["baseline_running_minutes"] < BASELINE_MIN:
        reasons.append(f"Learning this pump's normal: {out['baseline_running_minutes']} of {BASELINE_MIN} running minutes seen.")
        severity = max(severity, 1)

    # 4. quality flags
    if "quality_any" in f:
        q = f["quality_any"].fillna(0).astype(int)
        last60 = q[f["_t"] > now - pd.Timedelta(minutes=60)]
        out["quality"]["flagged_total"] = int((q != 0).sum())
        out["quality"]["flagged_last_60"] = int((last60 != 0).sum())
        bits: dict[str, int] = {}
        for b, n in QUALITY_BITS.items():
            c = int(((q.to_numpy() & b) != 0).sum())
            if c:
                bits[n] = c
        out["quality"]["bits"] = bits
        if out["quality"]["flagged_last_60"] >= 6:
            names = ", ".join(n for b, n in QUALITY_BITS.items() if (last60.to_numpy() & b).any())
            reasons.append(f"{out['quality']['flagged_last_60']} of the last 60 minutes carry quality flags ({names}).")
            severity = max(severity, 2)

    out["status"] = {0: "OK", 1: "BASELINE_LEARNING", 2: "DEGRADED", 3: "INSUFFICIENT_DATA", 4: "NO_DATA"}[severity]
    out["reasons"] = reasons if reasons else ["All expected channels are delivering fresh values."]
    return out
