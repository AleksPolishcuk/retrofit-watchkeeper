"""The scenario table on the Proof tab (web/src/scenarios.ts) must not drift from the probe, the tests and the docs."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TS = (ROOT / "web" / "src" / "scenarios.ts").read_text(encoding="utf-8")
LISTED = set(re.findall(r"id: '(A\d\d)'", TS))


def test_the_table_lists_all_eighteen_situations():
    assert LISTED == {f"A{i:02d}" for i in range(1, 19)}


def test_every_scenario_the_probe_ran_is_in_the_table():
    probe = (ROOT / "eval" / "results" / "scenarios_probe.md").read_text(encoding="utf-8")
    ran = {m[:3] for m in re.findall(r"^\| (A\d\d[a-z]?) \|", probe, flags=re.M)}
    assert ran and ran <= LISTED


def test_every_scenario_a_test_covers_is_in_the_table():
    src = (ROOT / "tests" / "test_scenarios.py").read_text(encoding="utf-8")
    covered = {m.upper() for m in re.findall(r"def test_(?:e2e_)?(a\d\d)_", src)}
    assert covered and covered <= LISTED


def test_the_two_known_gaps_are_stated_in_the_readme_and_the_technical_note():
    gaps = set(re.findall(r"id: '(A\d\d)'[^}]*?status: 'gap'", TS, flags=re.S))
    assert gaps == {"A06", "A12"}
    for f in ("README.md", "docs/TECHNICAL_NOTE.md"):
        text = (ROOT / f).read_text(encoding="utf-8")
        assert "2 known gaps" in text or "2 are known gaps" in text, f


def test_the_counts_in_the_docs_match_the_table():
    statuses = re.findall(r"status: '(handled|partly|gap)'", TS)
    counts = {k: statuses.count(k) for k in ("handled", "partly", "gap")}
    assert counts == {"handled": 11, "partly": 5, "gap": 2}
    for f in ("README.md", "docs/TECHNICAL_NOTE.md", "submission/SUBMISSION.md"):
        text = (ROOT / f).read_text(encoding="utf-8")
        assert re.search(r"11 (are )?handled", text) and "5 partly" in text, f
