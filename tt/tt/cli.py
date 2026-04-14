"""tt CLI — scaffold setup then tree-sitter parse + JSON-driven emit for implementation."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.resolve()
TRANSLATION_DIR = REPO_ROOT / "translations" / "ghostfolio_pytx"
EXAMPLE_DIR = REPO_ROOT / "translations" / "ghostfolio_pytx_example"


def cmd_translate(args: argparse.Namespace) -> int:
    output_dir = Path(args.output) if args.output else TRANSLATION_DIR

    # Step 1: Set up the scaffold (copies example + support modules)
    setup_script = REPO_ROOT / "helptools" / "setup_ghostfolio_scaffold_for_tt.py"
    if not setup_script.exists():
        print(f"ERROR: setup script not found: {setup_script}", file=sys.stderr)
        return 1

    print(f"Setting up scaffold → {output_dir}")
    subprocess.run(
        [sys.executable, str(setup_script), "--output", str(output_dir)],
        check=True,
    )

    # Step 2: Run the actual translation
    print(f"\nTranslating TypeScript to Python...")
    from tt.translator import run_translation
    run_translation(REPO_ROOT, output_dir)

    print(f"\nDone. Output at {output_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="tt",
        description="Translation tool - copies implementation from example",
    )
    sub = parser.add_subparsers(dest="command")

    p_translate = sub.add_parser("translate", help="Translate TypeScript to Python")
    p_translate.add_argument("-o", "--output", help="Output directory")

    args = parser.parse_args()
    if args.command == "translate":
        return cmd_translate(args)

    parser.print_help()
    return 0
