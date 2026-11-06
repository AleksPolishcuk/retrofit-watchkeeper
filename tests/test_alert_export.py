import json
from pathlib import Path

import pandas as pd
from jsonschema import Draft202012Validator

from watchkeeper.alerts.export import parse_evidence, to_contract, write_alerts

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = Draft202012Validator(json.loads((ROOT / "docs" / "alert.schema.json").read_text(encoding="utf-8")))
ASSETS = pd.DataFrame([{"asset_id": "PUMP-08", "channels_available": "ambient_temp_c|bearing_temp_c|discharge_pressure_kpa|motor_current_a"}])


def _row(ft="SUCTION_STRAINER_CLOGGING", cls="MACHINE", ev="B1 mode-aware z: suction_pressure_kpa z=-6.2, motor_speed_rpm z=+3.9", t="2025-09-10T06:15:00Z"):
    return {"asset_id": "PUMP-08", "alert_time_utc": t, "event_class": cls, "fault_type": ft, "confidence": 0.7,
            "evidence": ev, "recommended_action": "Inspect and clean the strainer."}


def test_parse_evidence_patterns():
    items = parse_evidence("B1 mode-aware z: motor_speed_rpm z=+6.2, discharge_pressure_kpa z=-6.4")
    assert [(i["channel"], i["z"]) for i in items] == [("motor_speed_rpm", 6.2), ("discharge_pressure_kpa", -6.4)]
    assert parse_evidence("B1 mode-aware z: bearing_temp_c frozen")[0] == {"channel": "bearing_temp_c", "text": "constant value while the pump runs", "z": None}
    assert parse_evidence("B1 mode-aware z: missing rows")[0]["channel"] == "GATEWAY"
    alone = parse_evidence("B1 mode-aware z: flow_m3_h deviates alone (z=-5.4)")[0]
    assert alone["channel"] == "flow_m3_h" and alone["z"] == -5.4
    assert parse_evidence("") == []


def test_alerts_validate_against_the_contract():
    pred = pd.DataFrame([_row(), _row("SENSOR_STUCK", "SENSOR", "B1 mode-aware z: bearing_temp_c frozen", "2025-09-11T01:00:00Z"),
                         _row("COMMUNICATION_LOSS", "SENSOR", "B1 mode-aware z: missing rows", "2025-09-12T01:00:00Z"),
                         _row("UNKNOWN", "MACHINE", "B1 mode-aware z: ", "2025-09-13T01:00:00Z")])
    alerts = to_contract(pred, ASSETS, "test")
    assert [e.message for a in alerts for e in VALIDATOR.iter_errors(a)] == []
    assert alerts[2]["uncertainty"]["data_quality"] == "poor"
    assert alerts[3]["sensor_check"]["verdict"] == "unclear"
    assert alerts[1]["sensor_check"]["verdict"] == "sensor"
    assert all(a["requires_human_approval"] is True for a in alerts)


def test_missing_channels_follow_the_asset_instrumentation():
    alert = to_contract(pd.DataFrame([_row()]), ASSETS, "test")[0]
    assert set(alert["uncertainty"]["missing_channels"]) == {"suction_pressure_kpa", "flow_m3_h", "vibration_rms_mm_s", "motor_winding_temp_c"}


def test_alert_ids_stay_unique_when_two_alerts_share_a_minute():
    alerts = to_contract(pd.DataFrame([_row(), _row("CAVITATION")]), ASSETS, "test")
    assert len({a["alert_id"] for a in alerts}) == 2


def test_write_alerts_creates_a_file_per_asset_even_when_empty(tmp_path):
    alerts = to_contract(pd.DataFrame([_row()]), ASSETS, "test")
    paths = write_alerts(alerts, tmp_path, ["PUMP-08", "PUMP-09"])
    assert sorted(p.name for p in paths) == ["PUMP-08.json", "PUMP-09.json"]
    assert json.loads((tmp_path / "PUMP-09.json").read_text()) == []


def test_cavitation_alert_explains_that_the_evidence_is_a_calculation():
    pred = pd.DataFrame([_row("CAVITATION", "MACHINE", "WK causal+learned: npsh_margin=0.62")])
    alert = to_contract(pred, ASSETS, "test")[0]
    assert alert["evidence"][0]["channel"].startswith("npsh_margin")
    assert "0.62" in alert["evidence"][0]["text"]
    assert "calculated" in alert["sensor_check"]["reason"]
    assert [e.message for e in VALIDATOR.iter_errors(alert)] == []
