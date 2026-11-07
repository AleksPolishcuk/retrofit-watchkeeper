"""Live replay ingest: raw messages -> minutes -> detector. Read-only, tolerant, and equal to the batch path."""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from watchkeeper.ingest import MinuteAggregator, rows_to_frame

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TOPIC = "retrofit/site/PUMP-X/telemetry"


def msg(sec, minute=0, topic=TOPIC, **fields):
    ts = f"2025-01-01T00:{minute:02d}:{sec:02d}+00:00"
    return {"topic": topic, "payload": {"timestamp_utc": ts, "operating_mode": "RUNNING", "quality_flags": 0, **fields}}


def one_minute(minute=0, n=60, **extra):
    return [msg(s, minute, motor_current_a=10.0 + s, **extra) for s in range(n)]


def run(messages, **kw):
    agg = MinuteAggregator(**kw)
    rows = []
    for m in messages:
        rows += agg.feed(m)
    rows += agg.flush()
    return agg, rows


def test_a_minute_has_the_statistics_the_organizers_use():
    msgs = [msg(s, 0, motor_current_a=float(s), suction_pressure_kpa=50.0 if s < 10 else None) for s in range(60)]
    msgs[5]["payload"]["quality_flags"] = 2
    msgs[6]["payload"]["quality_flags"] = 8
    msgs[7]["payload"]["operating_mode"] = "STOPPED"
    _, rows = run(msgs)
    assert len(rows) == 1
    r = rows[0]
    v = np.arange(60, dtype=float)
    assert r["motor_current_a__mean"] == pytest.approx(v.mean())
    assert r["motor_current_a__std"] == pytest.approx(v.std(ddof=1))
    assert (r["motor_current_a__min"], r["motor_current_a__max"], r["motor_current_a__count"]) == (0.0, 59.0, 60)
    assert r["suction_pressure_kpa__count"] == 10                      # seconds 0 to 9; the None values never arrived
    assert r["operating_mode"] == "RUNNING" and r["running_fraction"] == pytest.approx(59 / 60)
    assert r["quality_any"] == 2 | 8 and r["rows"] == 60


def test_duplicates_are_kept_once_and_counted():
    msgs = one_minute() + [msg(10, 0, motor_current_a=20.0)]
    agg, rows = run(msgs)
    assert rows[0]["rows"] == 60 and agg.stats["duplicates"] == 1 and agg.stats["conflicts"] == 0
    msgs = one_minute() + [msg(10, 0, motor_current_a=99.0)]            # same second, different value: the last copy wins
    agg, rows = run(msgs)
    assert rows[0]["rows"] == 60 and agg.stats["conflicts"] == 1 and rows[0]["motor_current_a__max"] == 99.0


def test_messages_that_arrive_out_of_order_are_placed_correctly():
    ordered = one_minute() + one_minute(1)
    shuffled = list(ordered)
    shuffled[10], shuffled[40] = shuffled[40], shuffled[10]
    shuffled[3], shuffled[4] = shuffled[4], shuffled[3]
    agg, rows = run(shuffled, lateness_s=5)
    _, ref = run(ordered, lateness_s=5)
    assert agg.stats["out_of_order"] > 0 and agg.stats["late_dropped"] == 0
    assert pd.DataFrame(rows).equals(pd.DataFrame(ref))


def test_a_finished_minute_is_never_revised():
    agg = MinuteAggregator(lateness_s=5)
    out = []
    for m in one_minute() + one_minute(1)[:10]:
        out += agg.feed(m)
    assert len(out) == 1                                               # minute 0 finished once a message 5 s past its end arrived
    assert agg.feed(msg(30, 0, motor_current_a=5.0)) == []
    assert agg.stats["late_dropped"] == 1
    assert [r["window_start_utc"] for r in agg.flush()] == [pd.Timestamp("2025-01-01T00:01:00Z")]


def test_only_telemetry_topics_are_read():
    bad = {"topic": "retrofit/site/PUMP-X/command", "payload": "not even a dict: must not be looked at"}
    agg, rows = run([bad, {"topic": "retrofit/site/PUMP-X/cmd/setpoint", "payload": {"timestamp_utc": "2025-01-01T00:00:00Z", "motor_speed_rpm": 1500}}] + one_minute())
    assert agg.stats["ignored_topic"] == 2 and len(rows) == 1


def test_bad_input_is_counted_and_skipped_not_fatal():
    agg = MinuteAggregator()
    lines = ["not json", "", '{"topic": "retrofit/s/PUMP-X/telemetry"}', '{"topic": 5, "payload": {}}',
             '{"topic": "retrofit/s/PUMP-X/telemetry", "payload": {"timestamp_utc": "yesterday"}}',
             '{"topic": "retrofit/s/PUMP-X/telemetry", "payload": {"operating_mode": "RUNNING"}}']
    for ln in lines:
        assert agg.feed_line(ln) == []
    assert agg.stats["malformed"] == 5                                 # the empty line is not a message
    good = json.dumps(msg(0, 0, motor_current_a="oops", flow_m3_h=3.0))
    agg.feed_line(good)
    rows = agg.flush()
    assert rows[0]["flow_m3_h__count"] == 1 and "motor_current_a__count" not in rows[0] and agg.stats["messages"] == 6


def test_a_channel_that_stops_has_count_zero_and_no_mean():
    agg = MinuteAggregator(channels={"PUMP-X": ["motor_current_a", "suction_pressure_kpa"]})
    msgs = [msg(s, 0, motor_current_a=1.0, suction_pressure_kpa=2.0) for s in range(60)] + [msg(s, 1, motor_current_a=1.0) for s in range(60)]
    rows = []
    for m in msgs:
        rows += agg.feed(m)
    rows += agg.flush()
    f = rows_to_frame(rows)
    assert list(f.suction_pressure_kpa__count) == [60, 0] and np.isnan(f.suction_pressure_kpa__mean.iloc[1])


def test_the_ingest_package_has_no_write_or_subscribe_path():
    src = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "src" / "watchkeeper" / "ingest").glob("*.py"))
    assert not re.search(r"\.publish\(|\.subscribe\(|import paho|mqtt\.Client|requests\.(post|put)|socket\.", src)
    live = (ROOT / "src" / "watchkeeper" / "api" / "app.py").read_text(encoding="utf-8")
    assert "@app.post" not in live and "@app.put" not in live and "@app.delete" not in live


needs_data = pytest.mark.skipif(not (DATA / "features_1min.parquet").exists(), reason="data pack not linked")
needs_model = pytest.mark.skipif(not (ROOT / "models" / "wk.joblib").exists(), reason="model not built")


@needs_data
@pytest.mark.parametrize("asset", ["PUMP-08", "PUMP-04", "PUMP-03"])        # a retrofit, a fully instrumented and a legacy pump
def test_minutes_from_raw_messages_equal_the_organizers_features(asset):
    from retrofit_sim.replay import messages
    assets = pd.read_csv(DATA / "assets.csv").set_index("asset_id")
    row = assets.loc[asset]
    start = pd.Timestamp(row["window_start_utc"])
    end = start + pd.Timedelta(minutes=90)
    agg = MinuteAggregator(lateness_s=5, channels={asset: str(row["channels_available"]).split("|")})
    rows = []
    for m in messages(DATA, asset, start.isoformat(), end.isoformat(), site=row["site"]):
        rows += agg.feed(m)
    rows += agg.flush()
    mine = rows_to_frame(rows)
    ref = pd.read_parquet(DATA / "features_1min.parquet", filters=[("asset_id", "==", asset)])
    ref = ref[(ref.window_start_utc >= start) & (ref.window_start_utc < end)].reset_index(drop=True)
    assert len(mine) == len(ref) == 90
    assert (mine.window_start_utc.values == ref.window_start_utc.values).all()
    for c in ref.columns:
        if c in ("asset_id", "window_start_utc") or c not in mine.columns:
            continue
        a, b = mine[c], ref[c]
        if a.dtype == object or b.dtype == object:
            assert (a.astype(str).values == b.astype(str).values).all(), c
            continue
        assert (a.notna() == b.notna()).all(), c
        both = (a.notna() & b.notna()).to_numpy()
        np.testing.assert_allclose(a.to_numpy(float)[both], b.to_numpy(float)[both], rtol=1e-5, atol=1e-3, err_msg=c)


@needs_data
@needs_model
def test_live_runner_alerts_equal_the_batch_alerts_and_the_state_file_is_clean_json(tmp_path):
    from watchkeeper.diagnose import DiagnosisModel
    from watchkeeper.evalkit import DevData
    from watchkeeper.ingest.live import LiveRunner
    from watchkeeper.methods import METHODS
    assets = pd.read_csv(DATA / "assets.csv")
    model = DiagnosisModel.load(ROOT / "models" / "wk.joblib")
    asset, end = "PUMP-08", pd.Timestamp("2025-09-10T10:00:00Z")                    # the first alert of this validation pump is at 09:33
    ref = pd.read_parquet(DATA / "features_1min.parquet", filters=[("asset_id", "==", asset)])
    ref = ref[ref.window_start_utc < end].reset_index(drop=True)
    runner = LiveRunner(asset, assets, model, tmp_path, every=1500)
    for rec in ref.to_dict("records"):
        runner._take([rec])
    state = runner.finish()
    batch = METHODS["wk"]().predict(model, DevData(Path("."), assets, ref, pd.DataFrame(columns=["asset_id"]), pd.DataFrame(), pd.DataFrame()), asset)
    assert len(batch) >= 1
    assert [(a["alert_time_utc"], a["fault_type"]) for a in state["alerts"]] == [(pd.Timestamp(t).strftime("%Y-%m-%dT%H:%M:%SZ"), f) for t, f in zip(batch.alert_time_utc, batch.fault_type)]
    assert state["status"] == "finished" and state["minutes"] == len(ref) and state["health"]["status"] in {"OK", "DEGRADED", "BASELINE_LEARNING"}
    text = (tmp_path / asset / "state.json").read_text(encoding="utf-8")
    parsed = json.loads(text, parse_constant=lambda c: pytest.fail(f"{c} in state file"))
    assert parsed["alerts"][0]["alert_id"] in parsed["alert_log"]
    assert not list((tmp_path / asset).glob("*.tmp"))


@needs_data
def test_live_replay_refuses_a_test_pump():
    from watchkeeper.ingest.live import main
    with pytest.raises(SystemExit) as e:
        main(["--asset", "PUMP-10", "--input", "/dev/null"])
    assert "test pump" in str(e.value)


@needs_data
def test_api_serves_live_state_read_only(tmp_path):
    from fastapi.testclient import TestClient
    from watchkeeper.api.app import create_app
    live = tmp_path / "live"
    (live / "PUMP-08").mkdir(parents=True)
    (live / "PUMP-08" / "state.json").write_text(json.dumps({"asset_id": "PUMP-08", "status": "running", "as_of_utc": "2025-09-10T10:00:00Z", "minutes": 3600,
                                                              "alerts": [{"alert_id": "a"}], "health": {"status": "OK"}}), encoding="utf-8")
    (live / "PUMP-10").mkdir()
    (live / "PUMP-10" / "state.json").write_text("{}", encoding="utf-8")
    c = TestClient(create_app(DATA, alerts_dir=tmp_path / "none", live_dir=live))
    assert c.get("/api/live").json() == [{"asset_id": "PUMP-08", "status": "running", "as_of_utc": "2025-09-10T10:00:00Z", "minutes": 3600, "alerts": 1, "health": "OK", "updated_wall_utc": None}]
    assert c.get("/api/live/PUMP-08").json()["minutes"] == 3600
    assert c.get("/api/live/PUMP-09").status_code == 404
    assert c.get("/api/live/PUMP-10").status_code == 403                  # test pumps are not served, even when a file exists
    assert c.get("/api/live/PUMP-99").status_code == 404
    assert c.post("/api/live/PUMP-08").status_code == 405
