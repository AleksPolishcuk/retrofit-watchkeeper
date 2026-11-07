"""The alert contract between the engine and the interface: every committed alert must validate."""
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


ENGINE = sorted((ROOT / "artifacts" / "alerts").glob("*.json"))


def _all():
    return [a for p in ENGINE for a in json.loads(p.read_text(encoding="utf-8"))]


def test_the_committed_alerts_cover_the_cases_the_interface_must_show():
    alerts = _all()
    assert len(alerts) >= 90 and len(ENGINE) == 12
    assert {a["event_class"] for a in alerts} == {"MACHINE", "SENSOR"}
    assert any(a["fault_type"] == "UNKNOWN" or a.get("uncertainty", {}).get("missing_channels") for a in alerts)
    assert all(a["requires_human_approval"] is True for a in alerts)


def test_alert_ids_are_unique():
    ids = [a["alert_id"] for a in _all()]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("path", sorted((ROOT / "artifacts" / "alerts").glob("*.json")) if (ROOT / "artifacts" / "alerts").exists() else [])
def test_engine_output_validates(path):
    alerts = json.loads(path.read_text(encoding="utf-8"))
    assert _errors(alerts) == []
    assert all(a["asset_id"] == path.stem for a in alerts)
