#!/usr/bin/env python3
"""
evaluate/scoring/overall.py — combined overall score (70% tests, 30% code quality).

Imports results from successfultests and codequality and prints a single
weighted score.  Tests contribute 70%, quality contributes 30%.

Usage:
  uv run --project tt python evaluate/scoring/overall.py
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.resolve()
SCORING_DIR = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

_GRADE_THRESHOLDS = [(90, "A"), (75, "B"), (60, "C"), (45, "D")]


def _grade(score: float) -> str:
    for threshold, letter in _GRADE_THRESHOLDS:
        if score >= threshold:
            return letter
    return "F"


def _load_module(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def main() -> int:
    tests_mod = _load_module("successfultests", SCORING_DIR / "successfultests.py")
    quality_mod = _load_module("codequality", SCORING_DIR / "codequality.py")

    tests_result = tests_mod.run()
    quality_result = quality_mod.run()

    tests_pct = tests_result.get("percentage", 0.0)
    quality_pct = quality_result.get("weighted_score", 0.0)
    overall = round((tests_pct * 0.7 + quality_pct * 0.3), 2)
    grade = _grade(overall)

    print()
    print("=" * 70)
    print("  Overall Score")
    print("=" * 70)
    print(f"  Successful tests   {tests_pct:5.1f}/100  (weight=70%)")
    print(f"  Code quality       {quality_pct:5.1f}/100  (weight=30%)")
    print(f"  {'─' * 40}")
    print(f"  Overall            {overall:5.1f}/100  grade={grade}")
    print("=" * 70)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
