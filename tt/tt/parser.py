"""tree-sitter TypeScript parsing — no project-specific strings."""
from __future__ import annotations

from tree_sitter import Language
from tree_sitter import Parser as TSParser
from tree_sitter import Tree

_PARSER: TSParser | None = None


def get_ts_parser() -> TSParser:
    """Return a configured Parser for TypeScript (not TSX)."""
    global _PARSER
    if _PARSER is not None:
        return _PARSER
    import tree_sitter_typescript as tst

    p = TSParser()
    p.language = Language(tst.language_typescript())
    _PARSER = p
    return p


def parse_typescript(source: bytes) -> Tree:
    """Parse UTF-8 encoded TypeScript source into a syntax tree."""
    return get_ts_parser().parse(source)
