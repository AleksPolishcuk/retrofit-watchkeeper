"""Alert snapshots per model version: kept, never overwritten, listed read-only."""
import json
from pathlib import Path

import pytest

from watchkeeper.alerts.archive import archive_alerts, archive_dir, main, read_index

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def alert(asset="PUMP-08", t="2025-09-10T09:33:00Z", version="wk-aaa", fault="BEARING_WEAR"):
    return {"alert_id": f"{asset}-{t}", "asset_id": asset, "alert_time_utc": t, "fault_type": fault, "model_version": version}


def test_one_snapshot_per_version_and_pump_with_an_index(tmp_path):
    new = archive_alerts([alert(), alert(t="2025-09-11T00:00:00Z"), alert("PUMP-09"), alert(version="wk-bbb")], tmp_path, "2026-11-07T15:00:00Z")
    assert {(e["model_version"], e["asset_id"], e["alerts"]) for e in new} == {("wk-aaa", "PUMP-08", 2), ("wk-aaa", "PUMP-09", 1), ("wk-bbb", "PUMP-08", 1)}
    assert (tmp_path / "wk-aaa" / "PUMP-08.json").exists() and (tmp_path / "wk-bbb" / "PUMP-08.json").exists()
    assert len(read_index(tmp_path)) == 3 and len(read_index(tmp_path, "PUMP-09")) == 1


def test_an_identical_snapshot_is_not_written_twice(tmp_path):
    archive_alerts([alert()], tmp_path, "2026-11-07T15:00:00Z")
    assert archive_alerts([alert()], tmp_path, "2026-11-07T16:00:00Z") == []
    assert len(read_index(tmp_path)) == 1


def test_a_changed_result_for_the_same_version_never_overwrites_the_first_snapshot(tmp_path):
    archive_alerts([alert()], tmp_path, "2026-11-07T15:00:00Z")
    first = (tmp_path / "wk-aaa" / "PUMP-08.json").read_text()
    new = archive_alerts([alert(fault="MISALIGNMENT")], tmp_path, "2026-11-07T16:00:00Z")
    assert len(new) == 1 and new[0]["file"] != "wk-aaa/PUMP-08.json"
    assert (tmp_path / "wk-aaa" / "PUMP-08.json").read_text() == first
    assert len(list((tmp_path / "wk-aaa").glob("PUMP-08*.json"))) == 2


def test_unversioned_alerts_and_odd_version_names_are_kept_safely(tmp_path):
    a = alert(version="../evil name")
    b = {k: v for k, v in alert().items() if k != "model_version"}
    archive_alerts([a, b], tmp_path)
    assert (tmp_path / ".._evil_name" / "PUMP-08.json").exists() and (tmp_path / "unversioned" / "PUMP-08.json").exists()
    assert not (tmp_path.parent / "evil name").exists()


def test_a_directory_of_contract_files_can_be_archived_as_it_is(tmp_path):
    src = tmp_path / "alerts"
    src.mkdir()
    (src / "PUMP-08.json").write_text(json.dumps([alert(), alert(version="wk-bbb", t="2025-09-12T00:00:00Z")]), encoding="utf-8")
    (src / "broken.json").write_text("{not json", encoding="utf-8")
    out = tmp_path / "archive"
    assert len(archive_dir(src, out)) == 2
    assert main(["--from", str(src), "--out", str(out)]) == 0 and len(read_index(out)) == 2


@pytest.mark.skipif(not (DATA / "assets.csv").exists(), reason="data pack not linked")
def test_the_api_lists_snapshots_read_only(tmp_path):
    from fastapi.testclient import TestClient
    from watchkeeper.api.app import create_app
    archive_alerts([alert(), alert("PUMP-09", version="wk-bbb")], tmp_path / "arch", "2026-11-07T15:00:00Z")
    c = TestClient(create_app(DATA, alerts_dir=tmp_path / "none", archive_dir=tmp_path / "arch"))
    r = c.get("/api/alerts/archive", params={"asset_id": "PUMP-08"}).json()
    assert [(e["model_version"], e["alerts"]) for e in r] == [("wk-aaa", 1)]
    assert len(c.get("/api/alerts/archive").json()) == 2
    assert c.get("/api/alerts/archive", params={"asset_id": "PUMP-99"}).status_code == 404
    assert c.delete("/api/alerts/archive").status_code == 405 and c.post("/api/alerts/archive").status_code == 405
