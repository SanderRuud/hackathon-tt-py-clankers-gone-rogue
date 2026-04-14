"""Re-parse a TypeScript method body (statement_block text) as a standalone function."""
from __future__ import annotations

from tree_sitter import Node, Tree

from tt.parser import parse_typescript


def parse_wrapped_method(body_text: str) -> tuple[Tree, bytes, Node]:
    """Wrap body in a dummy function, parse, return tree, source bytes, statement_block node."""
    src = f"function __wrap(){body_text.strip()}\n".encode("utf-8")
    tree = parse_typescript(src)
    blk = _find_statement_block(tree.root_node)
    if blk is None:
        raise ValueError("no statement_block in wrapped method")
    return tree, src, blk


def _find_statement_block(root: Node) -> Node | None:
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type == "statement_block":
            return n
        for c in n.children:
            stack.append(c)
    return None
