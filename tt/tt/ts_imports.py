"""Resolve TypeScript ``ImportIR`` / symbol names into Python ``import`` lines (config-driven)."""
from __future__ import annotations

from typing import Any

from tt.ast_walker import FileIR


def python_lines_for_symbol_imports(
    files: list[FileIR],
    symbol_to_import_line: dict[str, str],
) -> list[str]:
    """Return unique Python import lines for TS symbols seen in ``files`` imports."""
    wanted: set[str] = set()
    for f in files:
        for imp in f.imports:
            for name in imp.names:
                if name in symbol_to_import_line:
                    wanted.add(symbol_to_import_line[name])
    return sorted(wanted)


def merge_cfg_import_lists(cfg: dict[str, Any], extra_from_ts: list[str]) -> list[str]:
    """Combine ``extra_imports`` from config with TS-derived import lines (dedupe order)."""
    base = list(cfg.get("extra_imports") or [])
    seen = set(base)
    out = list(base)
    for line in extra_from_ts:
        if line not in seen:
            seen.add(line)
            out.append(line)
    return out


def file_imports_summary(files: list[FileIR]) -> list[dict[str, Any]]:
    """Serialize imports for debugging / SOLUTION docs (no TS path literals required in tt)."""
    out: list[dict[str, Any]] = []
    for f in files:
        for imp in f.imports:
            out.append(
                {
                    "file": f.path_name,
                    "module": imp.module_spec,
                    "names": list(imp.names),
                }
            )
    return out
