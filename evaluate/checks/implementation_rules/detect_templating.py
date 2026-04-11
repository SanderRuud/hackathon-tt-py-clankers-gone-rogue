#!/usr/bin/env python3
"""
detect_templating.py — detect multiline code templates in tt/ that suggest
pre-generated code is being inserted into translations.

The tt tool should translate TypeScript to Python dynamically, not ship
pre-written Python code templates. This check finds multiline string literals
(triple-quoted strings) longer than 2 lines that appear to contain Python code.

Usage:
  python detect_templating.py
  pytest detect_templating.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
TT_ROOT = PROJECT_ROOT / "tt" / "tt"

# Python keywords that suggest a string contains code
CODE_INDICATORS = {
    "def ", "class ", "for ", "while ", "if ", "elif ", "else:",
    "return ", "import ", "from ", "try:", "except", "with ",
    "async def", "await ", "yield ", "lambda ", "raise "
}


def _looks_like_code(text: str) -> bool:
    """Return True if text appears to contain Python code."""
    lines = text.splitlines()
    if len(lines) <= 2:
        return False

    # Check if any line contains code indicators
    for line in lines:
        stripped = line.strip()
        if any(stripped.startswith(kw) or f" {kw}" in line for kw in CODE_INDICATORS):
            return True
    return False


def _is_docstring(node: ast.AST, parent: ast.AST | None) -> bool:
    """Check if a node is a docstring (leading string in module/function/class)."""
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        return False

    # Module docstring: first statement in Module body
    if isinstance(parent, ast.Module):
        if parent.body and isinstance(parent.body[0], ast.Expr):
            return parent.body[0].value is node

    # Function/class docstring: first statement in body
    if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        if parent.body and isinstance(parent.body[0], ast.Expr):
            return parent.body[0].value is node

    return False


def _is_assigned_or_returned(node: ast.Constant, parent: ast.AST | None, grandparent: ast.AST | None) -> bool:
    """Check if a string constant is assigned to a variable or returned."""
    # Direct assignment: x = "..."
    if isinstance(parent, (ast.Assign, ast.AnnAssign)):
        return True

    # Return statement: return "..."
    if isinstance(parent, ast.Return):
        return True

    # Also check if it's part of a call that looks like it's writing/returning code
    # e.g., write_file("code here") or similar
    if isinstance(parent, ast.Call):
        # This is an argument to a function call - might be legitimate
        # We'll be conservative and flag these
        return True

    return False


def scan() -> list[str]:
    """Find multiline string templates containing code in tt/."""
    if not TT_ROOT.exists():
        return []

    # Scan all Python files under tt/tt/
    tt_files = sorted(p for p in TT_ROOT.rglob("*.py") if p.is_file())

    violations: list[str] = []

    for path in tt_files:
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue

        # Build parent map for context checking
        parent_map: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parent_map[child] = parent

        # Walk AST looking for string constants
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value

                if not _looks_like_code(text):
                    continue

                parent = parent_map.get(node)
                grandparent = parent_map.get(parent) if parent else None

                # Skip docstrings
                if _is_docstring(node, parent):
                    continue

                # Skip strings in comments (they're not in the AST)
                # Skip strings that are just in expression statements (not assigned/returned)
                if isinstance(parent, ast.Expr):
                    # This is a standalone expression, not an assignment or return
                    continue

                # Only flag if it's being assigned or returned
                if not _is_assigned_or_returned(node, parent, grandparent):
                    continue

                # This looks like a code template being used
                lineno = node.lineno if hasattr(node, 'lineno') else 1
                line_count = len(text.splitlines())
                violations.append(
                    f"{path.relative_to(PROJECT_ROOT)}:{lineno}: "
                    f"{line_count}-line string template contains pre-generated code"
                )

    return violations


def test_no_templating():
    """tt must not use pre-generated code templates."""
    violations = scan()
    if violations:
        report = "\n".join(violations)
        raise AssertionError(
            f"Possible pre-generated code templates found ({len(violations)} finding(s)):\n{report}"
        )


if __name__ == "__main__":
    violations = scan()
    if violations:
        print("ALERT: Possible pre-generated code templates found!\n")
        for v in violations:
            print(f"  {v}")
        print(f"\n{len(violations)} finding(s) total.")
        sys.exit(1)
    else:
        print("OK: No pre-generated code templates found.")
        sys.exit(0)
