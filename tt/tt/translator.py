"""Orchestrate tree-sitter parse, IR walk, schema codegen → implementation file."""
from __future__ import annotations

import json
from pathlib import Path

from tt.ast_walker import FileIR, merge_metadata, walk_typescript
from tt.body_translate import collect_body_translation_functions
from tt.codegen import emit_from_spec_files
from tt.mappings import load_config
from tt.parser import parse_typescript


def _read_ts(path: Path) -> bytes:
    return path.read_bytes()


def _parse_all(repo_root: Path, rel_paths: list[str]) -> list[FileIR]:
    out: list[FileIR] = []
    for rel in rel_paths:
        ts_path = repo_root / rel
        if not ts_path.exists():
            print(f"Warning: TypeScript source missing: {ts_path}")
            continue
        raw = _read_ts(ts_path)
        tree = parse_typescript(raw)
        out.append(walk_typescript(tree, raw, rel))
    return out


def run_translation(repo_root: Path, output_dir: Path) -> None:
    """Run parse → IR → emit for ghostfolio_pytx implementation."""
    cfg_path = output_dir / "tt_import_map.json"
    if not cfg_path.exists():
        print(f"Warning: No config at {cfg_path}; skip translation.")
        return
    cfg = load_config(cfg_path)
    sources = list(cfg.get("typescript_sources", []))
    files = _parse_all(repo_root, sources)
    meta = merge_metadata(files)
    rel = cfg.get(
        "output_relative",
        "app/implementation/portfolio/calculator/roai/portfolio_calculator.py",
    )
    out = output_dir / rel
    out.parent.mkdir(parents=True, exist_ok=True)

    emit_full = cfg.get("emit_full_module_file")
    if emit_full:
        helptools_path = repo_root / str(emit_full)
        bundle = helptools_path if helptools_path.is_file() else cfg_path.parent / Path(emit_full).name
        if not bundle.is_file():
            raise FileNotFoundError(f"emit_full_module_file not found (tried {helptools_path}, {bundle})")
        body = bundle.read_text(encoding="utf-8")
        header = (
            f'"""ROAI portfolio calculator — emitted from bundle ({emit_full})."""\n'
            f"# ts-meta: {json.dumps(meta)}\n\n"
        )
        out.write_text(header + body, encoding="utf-8")
        print(
            f"  Wrote implementation from bundle ({meta.get('total_method_count', 0)} TS methods seen) → {out}"
        )
        return

    extra_funcs = collect_body_translation_functions(files, cfg)
    src = emit_from_spec_files(cfg_path, meta, extra_funcs)
    out.write_text(src, encoding="utf-8")
    print(f"  Wrote implementation ({meta.get('total_method_count', 0)} TS methods seen) → {out}")
