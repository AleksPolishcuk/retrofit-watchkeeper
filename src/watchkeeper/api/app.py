"""Read-only API. Every route is GET: there is no way to send a command to a machine through this service.

Alerts come from artifacts/alerts/<asset_id>.json (written by the engine) and fall back to docs/mock_alerts.json.
Telemetry series are only served for the nine dev pumps. The three test pumps (PUMP-10, 11, 12) are not served here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query

ROOT = Path(__file__).resolve().parents[3]
ASSET_FIELDS = ["asset_id", "split", "site", "system", "profile", "control", "instrumentation_tier", "window_start_utc",
                "window_end_utc", "commissioned_year", "motor_rated_kw", "fluid", "vibration_alarm_mm_s", "vibration_trip_mm_s"]
CHANNELS = ["motor_speed_rpm", "motor_current_a", "motor_power_kw", "suction_pressure_kpa", "discharge_pressure_kpa", "flow_m3_h",
            "fluid_temp_c", "bearing_temp_c", "motor_winding_temp_c", "vibration_rms_mm_s", "vibration_accel_rms_g",
            "vibration_crest_factor", "valve_position_pct"]


# What-if: which simulated action answers which diagnosis. The condition level is an assumption for illustration, because the detector does
# not estimate severity. Only these three have a matching intervention in the organizers' sandbox.
WHATIF = {
    "SUCTION_STRAINER_CLOGGING": ("clean_strainer", {"clog": 2.0}, "strainer clogged (assumed level 2.0)"),
    "BEARING_WEAR": ("replace_bearing", {"bearing_wear": 0.5}, "bearing wear at about half way to failure (assumed 0.5)"),
    "MISALIGNMENT": ("realign", {"misalignment": 0.5}, "moderate misalignment (assumed 0.5)"),
}
WHATIF_ROWS = [("flow_m3h", "Cooling flow", "m3/h"), ("duty_satisfaction", "Share of required flow", "x"), ("input_kw", "Electrical power", "kW"),
               ("vib_rms_mm_s", "Vibration", "mm/s"), ("bearing_temp_c", "Bearing temperature", "C"), ("npsh_margin", "NPSH margin", "x"),
               ("risk_proxy", "Risk proxy (0-1)", ""), ("energy_eur_per_day", "Energy cost", "EUR/day")]


def _clean(value):
    return None if isinstance(value, float) and pd.isna(value) else value


def create_app(data_dir=None, alerts_dir=None, mock_path=None) -> FastAPI:
    data_dir = Path(data_dir or os.environ.get("WATCHKEEPER_DATA", ROOT / "data"))
    alerts_dir = Path(alerts_dir or ROOT / "artifacts" / "alerts")
    mock_path = Path(mock_path or ROOT / "docs" / "mock_alerts.json")

    app = FastAPI(title="Watchkeeper API (read-only)", version="0.0.1")
    assets = pd.read_csv(data_dir / "assets.csv")
    by_id = {r["asset_id"]: r for r in assets.to_dict("records")}
    dev_ids = set(assets[assets.split.isin(["train", "validation"])].asset_id)
    events = pd.concat([pd.read_csv(data_dir / "events_train.csv"), pd.read_csv(data_dir / "events_validation.csv")], ignore_index=True)
    benign = pd.read_csv(data_dir / "benign_windows_train_validation.csv")
    feature_cache: dict[str, pd.DataFrame] = {}

    def need(asset_id: str) -> dict:
        if asset_id not in by_id:
            raise HTTPException(404, f"unknown asset {asset_id}")
        return by_id[asset_id]

    def load_alerts(asset_id: str | None):
        """Return (source, alerts). Engine file when it exists, otherwise the mock file."""
        if asset_id and (alerts_dir / f"{asset_id}.json").exists():
            return "engine", json.loads((alerts_dir / f"{asset_id}.json").read_text(encoding="utf-8"))
        if asset_id is None and alerts_dir.exists() and any(alerts_dir.glob("*.json")):
            merged = [a for p in sorted(alerts_dir.glob("*.json")) for a in json.loads(p.read_text(encoding="utf-8"))]
            return "engine", merged
        mock = json.loads(mock_path.read_text(encoding="utf-8")) if mock_path.exists() else []
        return "mock", [a for a in mock if asset_id is None or a["asset_id"] == asset_id]

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": "read-only"}

    @app.get("/api/assets")
    def list_assets():
        out = []
        for r in assets.to_dict("records"):
            source, alerts = load_alerts(r["asset_id"])
            item = {k: _clean(r.get(k)) for k in ASSET_FIELDS}
            item["channels_available"] = str(r["channels_available"]).split("|")
            item["alert_count"] = len(alerts)
            item["alert_source"] = source
            item["telemetry_served"] = r["asset_id"] in dev_ids
            out.append(item)
        return out

    @app.get("/api/alerts")
    def alerts_for(asset_id: str | None = None):
        if asset_id:
            need(asset_id)
        source, alerts = load_alerts(asset_id)
        return {"asset_id": asset_id, "source": source, "alerts": alerts}

    @app.get("/api/timeline")
    def timeline(asset_id: str):
        a = need(asset_id)
        dev = asset_id in dev_ids
        ev = events[events.asset_id == asset_id] if dev else events.iloc[0:0]
        bn = benign[benign.asset_id == asset_id] if dev else benign.iloc[0:0]
        keep = ["event_id", "event_class", "fault_type", "onset_utc", "detectable_utc", "action_deadline_utc", "end_utc", "severity", "observable"]
        return {"asset_id": asset_id, "window_start_utc": a["window_start_utc"], "window_end_utc": a["window_end_utc"],
                "labels_public": dev,
                "events": [{k: _clean(v) for k, v in r.items()} for r in ev[keep].to_dict("records")],
                "benign": [{k: _clean(v) for k, v in r.items()} for r in bn[["benign_type", "start_utc", "end_utc"]].to_dict("records")]}

    @app.get("/api/series")
    def series(asset_id: str, channel: str, step_min: int = Query(15, ge=1, le=240)):
        need(asset_id)
        if asset_id not in dev_ids:
            raise HTTPException(403, "telemetry is not served for the test pumps in this build")
        if channel not in CHANNELS:
            raise HTTPException(400, f"unknown channel {channel}")
        if str(by_id[asset_id]["channels_available"]).find(channel) < 0:
            raise HTTPException(404, f"{asset_id} has no {channel}")
        if asset_id not in feature_cache:
            cols = ["asset_id", "window_start_utc"] + [f"{c}__mean" for c in CHANNELS]
            df = pd.read_parquet(data_dir / "features_1min.parquet", filters=[("asset_id", "==", asset_id)])
            df = df[[c for c in cols if c in df.columns]].copy()
            df["window_start_utc"] = pd.to_datetime(df["window_start_utc"], utc=True)
            feature_cache[asset_id] = df.set_index("window_start_utc").sort_index()
        col = f"{channel}__mean"
        s = feature_cache[asset_id][col].dropna().resample(f"{step_min}min").mean().dropna()
        return {"asset_id": asset_id, "channel": channel, "step_min": step_min,
                "t": [t.strftime("%Y-%m-%dT%H:%M:%SZ") for t in s.index], "v": [round(float(v), 3) for v in s.values]}

    results_dir = ROOT / "eval" / "results"

    def read_json(path: Path):
        """JSON file or None. NaN in the report (an interval that could not be computed) becomes null."""
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda c: None)

    @app.get("/api/results")
    def results():
        """Measured results, the stage table behind the likelihood words, the edge footprint and the instrumentation tiers. All read from files."""
        tiers = []
        for tier, g in assets.groupby("instrumentation_tier"):
            sets = [set(str(c).split("|")) for c in g["channels_available"]]
            tiers.append({"tier": tier, "pumps": int(len(g)), "channels": [c for c in CHANNELS if all(c in s for s in sets)],
                          "sometimes": [c for c in CHANNELS if any(c in s for s in sets) and not all(c in s for s in sets)]})
        return {"report": read_json(results_dir / "final" / "report.json"), "stages": read_json(ROOT / "models" / "stages.json"),
                "footprint": read_json(results_dir / "footprint.json"), "tiers": tiers}

    whatif_cache: dict = {}

    @app.get("/api/whatif")
    def whatif(asset_id: str, time_utc: str, fault_type: str):
        """Simulation only. Compares the pump as it is with the pump after the matching maintenance action, in the organizers' sandbox."""
        need(asset_id)
        if fault_type not in WHATIF:
            return {"available": False, "simulation_only": True,
                    "message": "No simulated action is defined for this diagnosis; the recommendation stays a human decision."}
        key = (asset_id, time_utc, fault_type)
        if key not in whatif_cache:
            from retrofit_sim.sandbox import what_if
            action, hypothesis, assumed = WHATIF[fault_type]
            r = what_if(str(data_dir), asset_id, time_utc, action, None, hypothesis)
            out = {"available": True, "simulation_only": True, "accepted": bool(r.get("accepted")), "rejection_reasons": r.get("rejection_reasons", []),
                   "warnings": r.get("warnings", []), "action": action, "assumed_condition": assumed, "rows": [], "intervention": None,
                   "caveats": r.get("caveats", [])}
            if "baseline" in r:
                out["rows"] = [{"label": lab, "unit": unit, "baseline": r["baseline"].get(k), "proposed": r["proposed"].get(k)}
                               for k, lab, unit in WHATIF_ROWS if r["baseline"].get(k) is not None]
                iv = r["intervention"]
                out["intervention"] = {"stop_h": iv["stop_h"], "labour_h": iv["labour_h"], "parts_eur": iv["parts_eur"], "estimated_cost_eur": iv["estimated_cost_eur"]}
            whatif_cache[key] = out
        return whatif_cache[key]

    return app


app = create_app() if (Path(os.environ.get("WATCHKEEPER_DATA", ROOT / "data")) / "assets.csv").exists() else None
