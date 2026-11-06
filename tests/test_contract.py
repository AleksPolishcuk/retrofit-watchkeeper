"""The alert contract between Engine and Cockpit: mock alerts and engine output must validate."""
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "docs" / "alert.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)


def _errors(alerts):
    return [f"{a.get('alert_id', '?')}: {e.message}" for a in alerts for e in VALIDATOR.iter_errors(a)]


def test_schema_is_valid():
    Draft202012Validator.check_schema(SCHEMA)


def test_mock_alerts_validate():
    alerts = json.loads((ROOT / "docs" / "mock_alerts.json").read_text(encoding="utf-8"))
    assert len(alerts) >= 6
    assert _errors(alerts) == []


def test_mock_alerts_cover_the_cases_the_ui_must_show():
    alerts = json.loads((ROOT / "docs" / "mock_alerts.json").read_text(encoding="utf-8"))
    assert {a["event_class"] for a in alerts} == {"MACHINE", "SENSOR"}
    assert any(a["fault_type"] == "UNKNOWN" for a in alerts)
    assert any(a.get("uncertainty", {}).get("missing_channels") for a in alerts)
    assert all(a["requires_human_approval"] is True for a in alerts)


def test_alert_ids_are_unique():
    alerts = json.loads((ROOT / "docs" / "mock_alerts.json").read_text(encoding="utf-8"))
    ids = [a["alert_id"] for a in alerts]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("path", sorted((ROOT / "artifacts" / "alerts").glob("*.json")) if (ROOT / "artifacts" / "alerts").exists() else [])
def test_engine_output_validates(path):
    alerts = json.loads(path.read_text(encoding="utf-8"))
    assert _errors(alerts) == []
    assert all(a["asset_id"] == path.stem for a in alerts)
