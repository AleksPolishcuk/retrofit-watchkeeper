"""The recorded alerts the interface shows are committed, complete and tied to the submission, so a fresh clone works without training anything."""
import json
import subprocess
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
ALERTS = ROOT / "artifacts" / "alerts"
PUMPS = [f"PUMP-{i:02d}" for i in range(1, 13)]


def load(p):
    return json.loads((ALERTS / f"{p}.json").read_text(encoding="utf-8"))


def test_alert_files_exist_for_all_twelve_pumps_and_carry_the_fields_the_interface_filters_on():
    for p in PUMPS:
        assert (ALERTS / f"{p}.json").exists(), p
    alerts = [a for p in PUMPS for a in load(p)]
    assert alerts
    for a in alerts:
        assert a["stage"] in {"watch", "possible", "likely", "very_likely"}, a["alert_id"]
        assert a.get("incident_id") and a.get("model_version") and a["requires_human_approval"] is True, a["alert_id"]
    assert {a["stage"] for a in alerts} >= {"watch", "likely"}, "the priority filter needs more than one level to be useful"


def test_test_pump_alerts_are_exactly_the_submitted_csv():
    sub = pd.read_csv(ROOT / "submission" / "predictions_test.csv")
    shown = sorted((a["asset_id"], a["alert_time_utc"], a["fault_type"]) for p in ("PUMP-10", "PUMP-11", "PUMP-12") for a in load(p))
    assert shown == sorted(zip(sub.asset_id, sub.alert_time_utc, sub.fault_type))


@pytest.mark.skipif(not (ROOT / ".git").exists(), reason="not a git checkout")
def test_the_alert_files_are_tracked_by_git_so_a_pull_brings_them():
    out = subprocess.run(["git", "ls-files", "artifacts/alerts"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert {f"artifacts/alerts/{p}.json" for p in PUMPS} <= set(out)
    ignored = subprocess.run(["git", "check-ignore", "artifacts/live/x", "artifacts/alerts_archive/x"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert len(ignored) == 2, "live state and the archive must stay local"
