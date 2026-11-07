import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from watchkeeper.api.app import create_app

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
pytestmark = pytest.mark.skipif(not (DATA / "assets.csv").exists(), reason="data pack not linked")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    empty = tmp_path_factory.mktemp("no_engine_alerts")
    return TestClient(create_app(DATA, alerts_dir=empty))


def test_every_route_is_read_only(client):
    methods = set()
    for route in client.app.routes:
        methods |= set(getattr(route, "methods", None) or [])
    assert methods <= {"GET", "HEAD", "OPTIONS"}, f"unexpected methods: {methods}"


def test_assets_list_has_twelve_pumps_with_tiers(client):
    r = client.get("/api/assets").json()
    assert len(r) == 12
    assert {a["instrumentation_tier"] for a in r} == {"T0_LEGACY", "T1_RETROFIT", "T2_FULL"}
    assert {a["asset_id"] for a in r if not a["telemetry_served"]} == {"PUMP-10", "PUMP-11", "PUMP-12"}


def test_alerts_fall_back_to_mock_when_the_engine_has_written_nothing(client):
    r = client.get("/api/alerts", params={"asset_id": "PUMP-08"}).json()
    assert r["source"] == "mock" and len(r["alerts"]) >= 1
    assert all(a["asset_id"] == "PUMP-08" for a in r["alerts"])


def test_alerts_use_engine_file_when_present(tmp_path):
    alert = json.loads((ROOT / "docs" / "mock_alerts.json").read_text(encoding="utf-8"))[0]
    (tmp_path / "PUMP-08.json").write_text(json.dumps([alert]), encoding="utf-8")
    r = TestClient(create_app(DATA, alerts_dir=tmp_path)).get("/api/alerts", params={"asset_id": "PUMP-08"}).json()
    assert r["source"] == "engine" and len(r["alerts"]) == 1


def test_unknown_asset_is_404(client):
    assert client.get("/api/alerts", params={"asset_id": "PUMP-99"}).status_code == 404
    assert client.get("/api/timeline", params={"asset_id": "PUMP-99"}).status_code == 404


def test_timeline_has_labels_for_dev_pumps_only(client):
    dev = client.get("/api/timeline", params={"asset_id": "PUMP-08"}).json()
    assert dev["labels_public"] is True and len(dev["events"]) >= 1
    test = client.get("/api/timeline", params={"asset_id": "PUMP-10"}).json()
    assert test["labels_public"] is False and test["events"] == []


def test_series_for_dev_pump_and_refused_for_test_pump(client):
    r = client.get("/api/series", params={"asset_id": "PUMP-08", "channel": "discharge_pressure_kpa", "step_min": 30}).json()
    assert len(r["t"]) == len(r["v"]) > 100
    assert client.get("/api/series", params={"asset_id": "PUMP-10", "channel": "discharge_pressure_kpa"}).status_code == 403
    assert client.get("/api/series", params={"asset_id": "PUMP-08", "channel": "flow_m3_h"}).status_code == 404   # no flow meter on PUMP-08
    assert client.get("/api/series", params={"asset_id": "PUMP-08", "channel": "nope"}).status_code == 400


def test_whatif_compares_before_and_after_for_a_clogged_strainer(client):
    r = client.get("/api/whatif", params={"asset_id": "PUMP-08", "time_utc": "2025-09-10T12:38:00Z", "fault_type": "SUCTION_STRAINER_CLOGGING"}).json()
    assert r["available"] and r["simulation_only"] and r["accepted"]
    flow = next(x for x in r["rows"] if x["label"] == "Cooling flow")
    assert flow["proposed"] > flow["baseline"]                  # cleaning the strainer restores flow
    assert r["intervention"]["estimated_cost_eur"] > 0
    assert any("not connected to any controller" in c for c in r["caveats"])


def test_whatif_says_so_when_no_simulated_action_exists(client):
    r = client.get("/api/whatif", params={"asset_id": "PUMP-08", "time_utc": "2025-09-10T12:38:00Z", "fault_type": "SENSOR_DRIFT"}).json()
    assert r["available"] is False and r["simulation_only"] is True


def test_whatif_outside_the_data_window_is_refused_not_invented(client):
    r = client.get("/api/whatif", params={"asset_id": "PUMP-08", "time_utc": "2030-01-01T00:00:00Z", "fault_type": "BEARING_WEAR"}).json()
    assert r["accepted"] is False and r["rejection_reasons"]


def test_whatif_unknown_asset_is_404(client):
    assert client.get("/api/whatif", params={"asset_id": "PUMP-99", "time_utc": "2025-09-10T12:38:00Z", "fault_type": "BEARING_WEAR"}).status_code == 404


def test_results_endpoint_serves_measurements_and_tier_channels_from_files(client):
    r = client.get("/api/results").json()
    assert {t["tier"] for t in r["tiers"]} == {"T0_LEGACY", "T1_RETROFIT", "T2_FULL"}
    t0 = next(t for t in r["tiers"] if t["tier"] == "T0_LEGACY")
    t2 = next(t for t in r["tiers"] if t["tier"] == "T2_FULL")
    assert set(t0["channels"]) < set(t2["channels"])                    # the legacy set is a subset of the full set
    assert "stages" in r and "footprint" in r and "report" in r        # absent files give null, not an error
    json.dumps(r, allow_nan=False)                                       # no NaN leaks into the response
