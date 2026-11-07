"""Graded likelihood words for the operator, backed by counts from back-testing (see eval/run_levels.py)."""
from __future__ import annotations

import json
from pathlib import Path

STAGES = ["watch", "possible", "likely", "very_likely"]
EDGES = (0.35, 0.55, 0.75)
DEFAULT_PATH = Path(__file__).resolve().parents[2] / "models" / "stages.json"


def stage_of(confidence: float, edges=EDGES) -> str:
    return STAGES[sum(confidence >= e for e in edges)]


def load_basis(path=DEFAULT_PATH) -> dict | None:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
