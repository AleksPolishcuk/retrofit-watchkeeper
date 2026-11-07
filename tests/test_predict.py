"""The predict path must match the evaluation path and produce a file the organizers' scorer accepts."""
import warnings
from pathlib import Path

import pandas as pd
import pytest
from retrofit_sim.scoring import load_predictions, score

DATA = Path(__file__).resolve().parents[1] / "data"
pytestmark = [pytest.mark.skipif(not (DATA / "assets.csv").exists(), reason="data pack not linked"),
              pytest.mark.filterwarnings("ignore")]


def test_predict_from_a_saved_model_matches_the_evaluation_path_and_scores(tmp_path, monkeypatch):
    from watchkeeper import predict as P
    from watchkeeper.alerts.export import write_predictions_csv
    from watchkeeper.evalkit import load_dev, score_ids
    from watchkeeper.methods import WKMethod
    monkeypatch.setitem(P.METHODS, "wk30", lambda: WKMethod(trees=30))
    dev = load_dev(DATA)
    train_ids = [a for a in dev.ids if a != "PUMP-09"]
    m = WKMethod(trees=30)
    model = m.fit(dev, train_ids)
    model_file = tmp_path / "m.joblib"
    model.save(model_file)
    pred = P.predict_assets(["PUMP-09"], model_file, "wk30", DATA)       # the frozen file is loaded, nothing is trained here

    direct = m.predict(model, dev, "PUMP-09")
    cols = ["alert_time_utc", "event_class", "fault_type"]
    assert pred[cols].reset_index(drop=True).equals(direct[cols].reset_index(drop=True))      # same alerts through both paths

    csv = write_predictions_csv(pred, tmp_path / "p.csv")
    loaded = load_predictions(str(csv))                                 # the organizers' own loader accepts the format
    assert set(loaded.event_class) <= {"MACHINE", "SENSOR"}
    assert score_ids(pd.read_csv(csv), dev, ["PUMP-09"])["events_scored"] >= 1


def test_target_data_carries_no_labels():
    from watchkeeper.evalkit import load_dev
    from watchkeeper.predict import target_data
    t = target_data(load_dev(DATA), ["PUMP-10", "PUMP-11", "PUMP-12"])
    assert set(t.feat.asset_id) == {"PUMP-10", "PUMP-11", "PUMP-12"}
    assert len(t.events) == 0 and len(t.benign) == 0 and len(t.alarms) == 0


def test_predict_refuses_a_dirty_tree_without_the_flag(monkeypatch):
    from watchkeeper import predict as P
    monkeypatch.setattr(P, "_git", lambda *a: " M file.py" if a[:1] == ("status",) else "abc")
    with pytest.raises(SystemExit):
        P.main(["--assets", "PUMP-09", "--out", "/tmp/should_not_exist.csv"])
