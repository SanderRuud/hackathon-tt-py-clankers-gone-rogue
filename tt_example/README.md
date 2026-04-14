# tt_example — Minimal Translation Tool

This is the simplest possible `tt` implementation. It does **no actual translation** — it only sets up the scaffold from the example directory, giving you a working FastAPI server that passes ~30 tests with stub responses.

## Usage

```bash
# Set up scaffold only (no translation)
uv run --project tt_example tt_example translate

# Then run tests against it
rm -rf translations/ghostfolio_pytx/.venv
make spinup-and-test-ghostfolio_pytx
```

## What it does

1. Calls `helptools/setup_ghostfolio_scaffold_for_tt.py` which:
   - Copies `translations/ghostfolio_pytx_example/` as the base (HTTP endpoints)
   - Overlays support modules from `tt/tt/scaffold/ghostfolio_pytx/` (models, helpers, types)
2. That's it. No TypeScript files are translated.

## What you need to add

To make more tests pass, you need to implement actual translation logic that:

1. Reads TypeScript source files from `projects/ghostfolio/`
2. Translates them to Python
3. Writes the output to `translations/ghostfolio_pytx/apps/api/...`

The translated code must implement `RoaiPortfolioCalculator.get_symbol_metrics()` — see [PORTFOLIO_CALCULATOR_INTERFACE.md](../translations/ghostfolio_pytx_example/PORTFOLIO_CALCULATOR_INTERFACE.md).

## How it compares to the real tt

| Feature | tt_example | tt (real) |
|---------|-----------|-----------|
| Scaffold setup | Yes | Yes |
| TypeScript parsing | No | Regex-based passes |
| Import mapping | No | Via `helptools/translation_config/…/tt_project_config.py` (`CONFIG`) |
| Tests passing | ~30 (stubs only) | ~54 (with translated calculator) |
