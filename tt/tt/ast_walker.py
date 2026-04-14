"""Walk tree-sitter output into a small intermediate representation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

from tree_sitter import Node, Tree


@dataclass
class MethodIR:
    name: str
    body_text: str


@dataclass
class ClassIR:
    name: str
    extends_name: str | None
    methods: list[MethodIR] = field(default_factory=list)


@dataclass
class FileIR:
    path_name: str
    classes: list[ClassIR] = field(default_factory=list)


def _find_named_child(node: Node, *types: str) -> Node | None:
    for ch in node.children:
        if ch.type in types:
            return ch
    return None


def _iter_types(node: Node, types: set[str]) -> Iterator[Node]:
    stack = [node]
    while stack:
        cur = stack.pop()
        if cur.type in types:
            yield cur
        for ch in reversed(cur.children):
            stack.append(ch)


def _class_extends(class_node: Node, source: bytes) -> str | None:
    for ch in class_node.children:
        if ch.type != "heritage_clause":
            continue
        for inner in ch.children:
            if inner.type == "extends_clause":
                for idn in inner.children:
                    if idn.type in ("identifier", "nested_identifier", "type_identifier"):
                        return source[idn.start_byte : idn.end_byte].decode()
    return None


def _method_name(method_node: Node, source: bytes) -> str:
    for ch in method_node.children:
        if ch.type in ("property_identifier", "identifier"):
            return source[ch.start_byte : ch.end_byte].decode()
    return ""


def _extract_method(method_node: Node, source: bytes) -> MethodIR | None:
    name = _method_name(method_node, source)
    if not name:
        return None
    body = _find_named_child(method_node, "statement_block")
    if body is None:
        return None
    text = source[body.start_byte : body.end_byte].decode()
    return MethodIR(name=name, body_text=text)


def _extract_class(class_node: Node, source: bytes) -> ClassIR:
    name_node = _find_named_child(class_node, "type_identifier", "identifier")
    cname = ""
    if name_node is not None:
        cname = source[name_node.start_byte : name_node.end_byte].decode()
    extends = _class_extends(class_node, source)
    mlist: list[MethodIR] = []
    for m in _iter_types(class_node, {"method_definition"}):
        mir = _extract_method(m, source)
        if mir:
            mlist.append(mir)
    return ClassIR(name=cname, extends_name=extends, methods=mlist)


def walk_typescript(tree: Tree, source: bytes, label: str) -> FileIR:
    """Collect classes and methods from a parsed TypeScript file."""
    root = tree.root_node
    classes: list[ClassIR] = []
    for cn in _iter_types(root, {"class_declaration"}):
        classes.append(_extract_class(cn, source))
    return FileIR(path_name=label, classes=classes)


def merge_metadata(files: list[FileIR]) -> dict[str, object]:
    """Summarise IR for downstream codegen (comments / metrics)."""
    total_methods = 0
    names: list[str] = []
    for f in files:
        for c in f.classes:
            names.append(c.name)
            total_methods += len(c.methods)
    return {
        "class_names": names,
        "total_method_count": total_methods,
        "file_count": len(files),
    }
