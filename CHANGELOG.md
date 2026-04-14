# Changelog

All notable changes to this repository’s **translation tool (`tt/`)**, **helptools**, and **Ghostfolio Python translation tree** are documented here. Entries are derived from **git history** and from **Cursor continual-learning** session checkpoints (local hook state: `.cursor/hooks/state/continual-learning.json`, gitignored).

The format is inspired by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

- Nothing yet.

## [2026-04-14]

### Added

- **`helptools/roai_runtime.py`** — `RoaiPortfolioEngine` and helpers used by the hybrid emit path (ledger, performance chart, holdings/details shape).
- **`helptools/translation_config/ghostfolio_pytx/tt_project_config.py`** — single **`CONFIG`** dict: TypeScript source paths, hybrid flags, `body_translations`, and inline **`emit_spec`** (replaces separate JSON config files).
- **`tt/tt/roai_hybrid_emit.py`** — hybrid emit: copy runtime module, build thin `RoaiPortfolioCalculator` facade with `ast`, append TS-derived `_body_*` methods.
- **`translations/ghostfolio_pytx/tt_project_config.py`** — copied into the translation output by scaffold setup (same content as helptools canonical file).
- **`translations/ghostfolio_pytx/app/implementation/portfolio/calculator/roai/roai_runtime.py`** — emitted copy of `helptools/roai_runtime.py` when running `tt translate`.

### Changed

- **`tt/tt/translator.py`** — Loads **`tt_project_config.py`** via `load_project_config_module()` when present; falls back to legacy **`tt_import_map.json`**. Calls **`emit_from_spec()`** with resolved config directory. Hybrid path uses **`try_emit_roai_hybrid()`** first when `emit_roai_hybrid` is set in `CONFIG`.
- **`tt/tt/codegen.py`** — **`emit_from_spec()`** and **`_resolve_emit_spec()`**: prefer inline **`emit_spec`** on `CONFIG`, else sibling **`.py`** (`EMIT_SPEC`), else **`.json`** via `emit_spec_file`.
- **`tt/tt/mappings.py`** — **`load_project_config_module()`** for Python config; **`load_config()`** retained for JSON.
- **`helptools/setup_ghostfolio_scaffold_for_tt.py`** — Copies **`tt_project_config.py`** from **`helptools/translation_config/ghostfolio_pytx/`** into the output tree (keeps domain-heavy config **outside** `tt/tt/` for automated rule checks).
- **`SOLUTION.md`** — Expanded architecture (mermaid, module table, emit decision flow).
- **`COMPETITION_RULES.md`** — Documents **`tt_project_config.py`** / helptools layout as allowed project-specific configuration.
- **`tt/tt/cli.py`** — Docstring: config-driven emit (not JSON-only).
- **`tt_example/README.md`** — Points import mapping to helptools translation config.
- **`.gitignore`** — Ignores **`.cursor/hooks/state/continual-learning.json`** so local continual-learning hook state is not committed.

### Removed

- **`helptools/roai_portfolio_calculator_bundle.py`** — superseded by **`roai_runtime.py`** + hybrid facade emit.
- **`tt_import_map.json`** and **`calculator_emit.json`** from **`tt/tt/scaffold/ghostfolio_pytx/`** and **`translations/ghostfolio_pytx/`** — configuration inlined or moved into **`tt_project_config.py`**.

### Notes

- **`evaluate/`** must remain **unchanged** from **`origin/main`** for competition checks (`detect_evaluate_modification.py`). Do not edit checkers or commit dirty **`evaluate/checks/results/latest.json`**.
- **`projects/ghostfolio/CHANGELOG.md`** is upstream Ghostfolio history; this file is for **hackathon / tt** work only.
