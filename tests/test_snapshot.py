"""The static snapshot of the read-only API: same names as the interface asks for, no test-pump telemetry, nothing that needs a server."""
import json
from pathlib import Path

import pytest

from watchkeeper.snapshot import export_snapshot, snapshot_path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CASES = json.loads((ROOT / "web" / "tests" / "snapshot-cases.json").read_text(encoding="utf-8"))
TEST_PUMPS = ("PUMP-10", "PUMP-11", "PUMP-12")


@pytest.mark.parametrize("url,expected", CASES)
def test_snapshot_names_match_the_ones_the_browser_computes(url, expected):
    assert snapshot_path(url) == expected                      # web/tests/snapshot.test.ts checks the same list from the TypeScript side


def test_file_names_cannot_climb_out_of_the_folder():
    p = snapshot_path("/api/series?asset_id=../../etc&channel=x&step_min=10")
    assert p is not None and ".." not in p.split("/") and p.count("/") == 1


needs_data = pytest.mark.skipif(not (DATA / "assets.csv").exists(), reason="data pack not linked")


@needs_data
def test_export_writes_public_pumps_and_never_telemetry_of_the_test_pumps(tmp_path):
    m = export_snapshot(tmp_path, assets=["PUMP-08", "PUMP-10"], steps=(120,), whatif=False)
    assert m["skipped"] == [] and m["files"] > 10
    assert (tmp_path / "assets.json").exists() and (tmp_path / "alerts.json").exists() and (tmp_path / "manifest.json").exists()
    assert list((tmp_path / "series").glob("PUMP-08__*__120.json"))
    assert not list((tmp_path / "series").glob("PUMP-1*")) and not list((tmp_path / "data-health").glob("PUMP-1*"))
    t = json.loads((tmp_path / "timeline" / "PUMP-10.json").read_text(encoding="utf-8"))
    assert t["labels_public"] is False and t["events"] == []
    assert "CC BY 4.0" in json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))["attribution"]


@needs_data
def test_the_simulator_is_not_run_for_the_test_pumps(tmp_path):
    from fastapi.testclient import TestClient
    from watchkeeper.api.app import create_app
    c = TestClient(create_app(DATA, alerts_dir=ROOT / "artifacts" / "alerts", live_dir=tmp_path / "x", archive_dir=tmp_path / "y"))
    r = c.get("/api/whatif", params={"asset_id": "PUMP-10", "time_utc": "2025-07-22T00:00:00Z", "fault_type": "BEARING_WEAR"}).json()
    assert r["available"] is False and "test pumps" in r["message"]


@pytest.mark.skipif(not (ROOT / "web" / "public" / "snapshot" / "manifest.json").exists(), reason="snapshot not generated")
def test_the_committed_snapshot_is_complete_and_has_no_test_pump_telemetry():
    snap = ROOT / "web" / "public" / "snapshot"
    m = json.loads((snap / "manifest.json").read_text(encoding="utf-8"))
    assert m["skipped"] == [] and m["files"] == sum(1 for p in snap.rglob("*.json")) - 1
    assert not [p.name for p in (snap / "series").glob("*") if p.name.startswith(TEST_PUMPS)]
    assert not [p.name for p in (snap / "data-health").glob("*") if p.name.startswith(TEST_PUMPS)]
    # every alert the interface can open has its data check and its simulator answer
    alerts = json.loads((snap / "alerts.json").read_text(encoding="utf-8"))["alerts"]
    assets = {a["asset_id"]: a for a in json.loads((snap / "assets.json").read_text(encoding="utf-8"))}
    for a in alerts:
        assert snapshot_path(f"/api/whatif?asset_id={a['asset_id']}&time_utc={a['alert_time_utc']}&fault_type={a['fault_type']}") and (snap / snapshot_path(f"/api/whatif?asset_id={a['asset_id']}&time_utc={a['alert_time_utc']}&fault_type={a['fault_type']}")).exists()
        if assets[a["asset_id"]]["telemetry_served"]:
            assert (snap / snapshot_path(f"/api/data-health?asset_id={a['asset_id']}&as_of={a['alert_time_utc']}")).exists()
