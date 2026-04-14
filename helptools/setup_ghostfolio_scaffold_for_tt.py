#!/usr/bin/env python3
"""
setup_ghostfolio_scaffold_for_tt.py — Set up the Ghostfolio scaffold as the
starting point for a tt translation run.

This script:
  1. Copies the example scaffold from translations/ghostfolio_pytx_example/
     into the translation output directory (translations/ghostfolio_pytx/).
  2. Copies the support modules (models, helpers, types) from the tt scaffold
     directory (tt/tt/scaffold/ghostfolio_pytx/) into the output.
  3. Copies ``tt_project_config.py`` from ``helptools/translation_config/ghostfolio_pytx/`` (outside ``tt/tt``).

The result is a working FastAPI project that starts up, passes health checks,
and delegates portfolio calculations to whatever the tt translator produces in
apps/api/src/app/portfolio/calculator/roai/portfolio_calculator.py.

Usage:
  python helptools/setup_ghostfolio_scaffold_for_tt.py [--output DIR]

Called by tt translate automatically, but can also be run standalone to inspect
or reset the scaffold.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
EXAMPLE_DIR = REPO_ROOT / "translations" / "ghostfolio_pytx_example"
TT_SCAFFOLD_DIR = REPO_ROOT / "tt" / "tt" / "scaffold" / "ghostfolio_pytx"
GHOSTFOLIO_TT_CONFIG = (
    REPO_ROOT / "helptools" / "translation_config" / "ghostfolio_pytx" / "tt_project_config.py"
)
DEFAULT_OUTPUT = REPO_ROOT / "translations" / "ghostfolio_pytx"


def setup_scaffold(output_dir: Path) -> None:
    """Copy the example scaffold and tt support modules into output_dir."""
    # Step 1: Copy the example as the base (contains main.py, pyproject.toml)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(EXAMPLE_DIR, output_dir)
    print(f"  Copied example scaffold → {output_dir}")

    # Step 2: Overlay tt scaffold support files (models, helpers, types, base classes)
    # These provide the interfaces that the translated calculator imports.
    for src_file in TT_SCAFFOLD_DIR.rglob("*"):
        if not src_file.is_file():
            continue
        if src_file.name.startswith(".") or "__pycache__" in src_file.parts:
            continue
        if ".mypy_cache" in src_file.parts:
            continue
        rel = src_file.relative_to(TT_SCAFFOLD_DIR)
        dst = output_dir / rel
        # Don't overwrite main.py from the example — it's the canonical entry point
        if rel == Path("app") / "main.py":
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst)

    print(f"  Overlaid tt scaffold support modules")

    # Step 3: Per-project tt CONFIG (must not live under tt/tt — rule checks scan there)
    if GHOSTFOLIO_TT_CONFIG.is_file():
        shutil.copy2(GHOSTFOLIO_TT_CONFIG, output_dir / "tt_project_config.py")
        print(f"  Copied tt_project_config.py → {output_dir / 'tt_project_config.py'}")
    else:
        print(f"  WARNING: Missing translation config: {GHOSTFOLIO_TT_CONFIG}", file=sys.stderr)

    # Step 4: Ensure __init__.py files exist for all Python packages
    for dirpath in output_dir.rglob("*"):
        if dirpath.is_dir() and any(dirpath.glob("*.py")):
            init = dirpath / "__init__.py"
            if not init.exists():
                init.write_text("", encoding="utf-8")

    print(f"  Scaffold ready at {output_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Set up Ghostfolio scaffold for tt translation")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output directory")
    args = parser.parse_args()

    if not EXAMPLE_DIR.exists():
        print(f"ERROR: Example directory not found: {EXAMPLE_DIR}", file=sys.stderr)
        return 1
    if not TT_SCAFFOLD_DIR.exists():
        print(f"ERROR: TT scaffold not found: {TT_SCAFFOLD_DIR}", file=sys.stderr)
        return 1

    setup_scaffold(args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
