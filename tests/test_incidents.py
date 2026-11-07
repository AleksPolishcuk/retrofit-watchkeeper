import pandas as pd

from watchkeeper.incidents import assign_incidents, family_key, incident_summary


def _a(t, ft, ev="WK: x z=+6.0", asset="PUMP-01", conf=0.5, cls="MACHINE"):
    return {"asset_id": asset, "alert_time_utc": t, "event_class": cls, "fault_type": ft, "confidence": conf, "evidence": ev, "recommended_action": ""}


def test_alerts_of_one_family_close_in_time_form_one_incident():
    p = assign_incidents(pd.DataFrame([_a("2025-01-01T00:00:00Z", "BEARING_WEAR"), _a("2025-01-01T06:00:00Z", "MISALIGNMENT"), _a("2025-01-01T11:00:00Z", "IMBALANCE")]))
    assert p.incident_id.nunique() == 1                                    # all mechanical, each within 12 h of the previous


def test_a_long_quiet_gap_or_another_family_opens_a_new_incident():
    p = assign_incidents(pd.DataFrame([_a("2025-01-01T00:00:00Z", "BEARING_WEAR"), _a("2025-01-01T02:00:00Z", "SUCTION_STRAINER_CLOGGING"),
                                       _a("2025-01-02T10:00:00Z", "BEARING_WEAR")]))
    assert p.incident_id.nunique() == 3


def test_instrument_faults_group_by_the_affected_channel():
    assert family_key("SENSOR_DRIFT", "WK: suction_pressure_kpa deviates alone (z=-6.0)") == "instrument:suction_pressure_kpa"
    p = assign_incidents(pd.DataFrame([_a("2025-01-01T00:00:00Z", "SENSOR_DRIFT", "WK: suction_pressure_kpa deviates alone (z=-6.0)", cls="SENSOR"),
                                       _a("2025-01-01T03:00:00Z", "SENSOR_CALIBRATION_SHIFT", "WK: suction_pressure_kpa deviates alone (z=-7.0)", cls="SENSOR"),
                                       _a("2025-01-01T04:00:00Z", "SENSOR_DRIFT", "WK: flow_m3_h deviates alone (z=-6.0)", cls="SENSOR")]))
    assert p.incident_id.nunique() == 2


def test_pumps_never_share_incidents_and_no_alert_is_dropped():
    raw = pd.DataFrame([_a("2025-01-01T00:00:00Z", "BEARING_WEAR", asset="PUMP-01"), _a("2025-01-01T00:05:00Z", "BEARING_WEAR", asset="PUMP-02")])
    p = assign_incidents(raw)
    assert len(p) == 2 and p.incident_id.nunique() == 2


def test_summary_names_the_best_supported_type():
    s = incident_summary(pd.DataFrame([_a("2025-01-01T00:00:00Z", "MISALIGNMENT", conf=0.3), _a("2025-01-01T05:00:00Z", "BEARING_WEAR", conf=0.7)]))
    assert len(s) == 1 and s.fault_type.iloc[0] == "BEARING_WEAR" and s.alerts.iloc[0] == 2
