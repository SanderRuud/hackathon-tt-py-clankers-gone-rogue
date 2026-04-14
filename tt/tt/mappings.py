"""Load per-project translation config from JSON; apply generic transforms."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def load_config(path: Path) -> dict[str, Any]:
    """Parse tt_import_map.json (or any project config file)."""
    return json.loads(path.read_text(encoding="utf-8"))


def apply_text_rules(text: str, rules: list[dict[str, Any]]) -> str:
    """Apply ordered replace rules from config (no TT hardcoded TS paths)."""
    out = text
    for rule in rules:
        kind = rule.get("kind", "")
        if kind == "replace_all":
            out = out.replace(rule.get("old", ""), rule.get("new", ""))
        elif kind == "regex_sub":
            pat = rule.get("pattern", "")
            repl = rule.get("repl", "")
            flags = 0
            if rule.get("multiline"):
                flags |= re.MULTILINE | re.DOTALL
            out = re.sub(pat, repl, out, flags=flags)
    return out


def camel_to_snake(name: str) -> str:
    """Convert identifier casing generically (API shape only)."""
    step1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", step1).lower()


def resolve_import_line(key: str, table: dict[str, str]) -> str | None:
    """Look up optional extra import fragment from import_resolution map."""
    return table.get(key)
