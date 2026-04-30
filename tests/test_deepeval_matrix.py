"""DeepEval + pytest evaluation matrix.

Usage:
    pytest tests/test_deepeval_matrix.py -q

This test reads cases from ``eval/cases.json`` and writes a JSON matrix report to
``eval/results/latest.json``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Optional import to keep local development smooth when DeepEval isn't installed.
deepeval = pytest.importorskip("deepeval")

from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "eval" / "cases.json"
RESULTS_DIR = ROOT / "eval" / "results"
RESULTS_PATH = RESULTS_DIR / "latest.json"


@dataclass
class EvalRow:
    case_id: str
    prompt: str
    actual_output: str
    expected_output: str
    score: float
    passed: bool
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "prompt": self.prompt,
            "actual_output": self.actual_output,
            "expected_output": self.expected_output,
            "score": self.score,
            "passed": self.passed,
            "reason": self.reason,
        }


def _load_cases() -> List[Dict[str, str]]:
    with CASES_PATH.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload["cases"]


def _write_matrix(rows: List[EvalRow]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    avg_score = sum(r.score for r in rows) / len(rows)
    pass_count = sum(1 for r in rows if r.passed)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool": "deepeval",
        "summary": {
            "total": len(rows),
            "passed": pass_count,
            "failed": len(rows) - pass_count,
            "avg_score": round(avg_score, 4),
        },
        "rows": [r.to_dict() for r in rows],
    }
    with RESULTS_PATH.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


@pytest.mark.evaluation
@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["id"])
def test_deepeval_matrix(case: Dict[str, str], request: pytest.FixtureRequest) -> None:
    """Evaluate each scenario and emit a JSON matrix report."""
    metric = GEval(
        name="inside_out_persona_quality",
        criteria=(
            "Score whether the actual output matches the expected emotional tone, "
            "stays concise, and avoids echoing the prompt."
        ),
        evaluation_params=["input", "actual_output", "expected_output"],
        threshold=0.65,
    )

    test_case = LLMTestCase(
        input=case["prompt"],
        actual_output=case["actual_output"],
        expected_output=case["expected_output"],
    )

    metric.measure(test_case)

    row = EvalRow(
        case_id=case["id"],
        prompt=case["prompt"],
        actual_output=case["actual_output"],
        expected_output=case["expected_output"],
        score=float(metric.score),
        passed=bool(metric.success),
        reason=str(metric.reason or ""),
    )

    rows: List[EvalRow] = getattr(request.config, "_eval_rows", [])
    rows.append(row)
    setattr(request.config, "_eval_rows", rows)

    assert metric.success, f"{case['id']} failed with score={metric.score}: {metric.reason}"


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Persist matrix after pytest completes."""
    rows: List[EvalRow] = getattr(session.config, "_eval_rows", [])
    if rows:
        _write_matrix(rows)
