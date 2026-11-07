import pytest

from watchkeeper.stats import bootstrap, composite, poisson_upper


def _row(**kw):
    r = dict(n=10, tp=8, ep=2, days=7.0, tl=7.0, ty=5.0, cl=8.0)
    return dict(r, **kw)


def test_composite_matches_the_scorer_formula():
    # recall 0.8, precision 0.8, F1 0.8; timeliness 0.7; type 0.5; class 0.8; burden 1 - (2/7)/2
    expected = 100 * (0.35 * 0.8 + 0.2 * 0.7 + 0.25 * 0.5 + 0.1 * 0.8 + 0.1 * (1 - 2 / 7 / 2))
    assert composite([_row()]) == pytest.approx(expected)


def test_an_alert_free_detector_scores_ten():
    assert composite([_row(tp=0, ep=0, tl=0.0, ty=0.0, cl=0.0)]) == pytest.approx(10.0)


def test_bootstrap_interval_contains_the_point_estimate_and_widens_with_fewer_pumps():
    many = {f"P{i}": _row(tp=8 + (i % 3), ty=4.0 + (i % 4)) for i in range(12)}
    lo, mid, hi = bootstrap(many, reps=300)
    assert lo <= composite(list(many.values())) <= hi
    few = dict(list(many.items())[:3])
    assert (bootstrap(few, reps=300)[2] - bootstrap(few, reps=300)[0]) >= (hi - lo) * 0.8


def test_poisson_upper_bound_for_zero_events_is_the_rule_of_three():
    assert poisson_upper(0, 100.0) * 100 == pytest.approx(3.69, abs=0.02)       # 3.69 events at 97.5 percent one-sided
