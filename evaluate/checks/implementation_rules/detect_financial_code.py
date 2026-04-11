#!/usr/bin/env python3
"""
detect_financial_code.py — detect financial domain-specific code in tt/.

The tt tool should not contain prefabricated financial logic. This check
scans for domain-specific financial terms that suggest the translator has
hardcoded business logic rather than translating TypeScript generically.

Financial terms flagged (case-insensitive):
  realized, buy, qty, cost, unitprice, investment, performance,
  netperformance, averageprice

Usage:
  python detect_financial_code.py
  pytest detect_financial_code.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
TT_ROOT = PROJECT_ROOT / "tt" / "tt"

# Financial domain terms that should not appear in generic translation code
FINANCIAL_TERMS = [
    "realized",
    "buy",
    "qty",
    "cost",
    "unitprice",
    "investment",
    "performance",
    "netperformance",
    "averageprice",
]


def scan() -> list[str]:
    """Find financial domain terms in tt/ code."""
    if not TT_ROOT.exists():
        return []

    # Build a case-insensitive pattern matching any financial term as a word
    # Use \b for word boundaries to avoid matching substrings like "buy" in "buyer"
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(term) for term in FINANCIAL_TERMS) + r")\b",
        re.IGNORECASE
    )

    # Scan all Python files under tt/tt/
    # Exclude wrapper (which is intentionally copied and may reference financial terms)
    wrapper_root = TT_ROOT / "scaffold" / "ghostfolio_pytx" / "app" / "wrapper"
    tt_files = sorted(
        p for p in TT_ROOT.rglob("*.py")
        if p.is_file() and not p.is_relative_to(wrapper_root)
    )

    violations: list[str] = []

    for path in tt_files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue

        for lineno, line in enumerate(lines, start=1):
            # Skip comments
            if line.strip().startswith("#"):
                continue

            match = pattern.search(line)
            if match:
                term = match.group(1)
                violations.append(
                    f"{path.relative_to(PROJECT_ROOT)}:{lineno}: "
                    f"financial term '{term}' found — "
                    f"tt must not contain domain-specific financial logic"
                )

    return violations


def test_no_financial_code():
    """tt must not contain prefabricated financial domain logic."""
    violations = scan()
    if violations:
        report = "\n".join(violations)
        raise AssertionError(
            f"Financial domain code detected ({len(violations)} finding(s)):\n{report}"
        )


if __name__ == "__main__":
    violations = scan()
    if violations:
        print("ALERT: Financial domain terms found in tt/ code!\n")
        for v in violations:
            print(f"  {v}")
        print(f"\n{len(violations)} finding(s) total.")
        sys.exit(1)
    else:
        print("OK: No financial domain terms found.")
        sys.exit(0)
