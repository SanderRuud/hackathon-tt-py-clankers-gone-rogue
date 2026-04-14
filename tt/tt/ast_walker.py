"""Walk tree-sitter output into a small intermediate representation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

from tree_sitter import Node, Tree


@dataclass
class ParamIR:
    """Single formal parameter (TypeScript)."""

    name: str
    type_text: str | None
    optional: bool
    default_present: bool


@dataclass
class FieldIR:
    """Class field / property (TypeScript)."""

    name: str
    type_text: str | None
    access: str  # public | private | protected | ""


@dataclass
class ImportIR:
    """One import from a TypeScript module (for import → Python mapping)."""

    module_spec: str  # e.g. 'big.js' or '@ghostfolio/...'
    names: list[str]  # imported identifiers (may be empty for side-effect imports)


@dataclass
class MethodIR:
    name: str
    body_text: str
    params: list[ParamIR] = field(default_factory=list)
    return_type_text: str | None = None
    access: str = ""
    """public | private | protected | protected_readonly | """


@dataclass
class ClassIR:
    name: str
    extends_name: str | None
    fields: list[FieldIR] = field(default_factory=list)
    methods: list[MethodIR] = field(default_factory=list)


@dataclass
class FileIR:
    path_name: str
    classes: list[ClassIR] = field(default_factory=list)
    imports: list[ImportIR] = field(default_factory=list)


def _find_named_child(node: Node, *types: str) -> Node | None:
    for ch in node.children:
        if ch.type in types:
            return ch
    return None


def _txt(source: bytes, node: Node) -> str:
    return source[node.start_byte : node.end_byte].decode()


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
        if ch.type == "class_heritage":
            for inner in ch.children:
                if inner.type == "extends_clause":
                    for idn in inner.children:
                        if idn.type in ("identifier", "nested_identifier", "type_identifier"):
                            return _txt(source, idn)
        # Older/alternate grammar
        if ch.type == "heritage_clause":
            for inner in ch.children:
                if inner.type == "extends_clause":
                    for idn in inner.children:
                        if idn.type in ("identifier", "nested_identifier", "type_identifier"):
                            return _txt(source, idn)
    return None


def _method_name(method_node: Node, source: bytes) -> str:
    for ch in method_node.children:
        if ch.type in ("property_identifier", "identifier"):
            return _txt(source, ch)
    return ""


def _accessibility(method_node: Node, source: bytes) -> str:
    for ch in method_node.children:
        if ch.type == "accessibility_modifier":
            inner = _find_named_child(ch, "public", "private", "protected")
            if inner is not None:
                return _txt(source, inner)
            return _txt(source, ch).strip()
    return ""


def _type_annotation_text(node: Node | None, source: bytes) -> str | None:
    if node is None or node.type != "type_annotation":
        return None
    # Everything after ':' 
    inner = node.children
    parts: list[str] = []
    for c in inner:
        if c.type in (":",):
            continue
        parts.append(_txt(source, c))
    return "".join(parts).strip() or None


def _extract_params(formal_params: Node | None, source: bytes) -> list[ParamIR]:
    if formal_params is None:
        return []
    out: list[ParamIR] = []
    for ch in formal_params.children:
        if ch.type == "required_parameter":
            opt = False
            dfl = False
            name_n = _find_named_child(ch, "identifier", "pattern")
            if name_n is None:
                for x in ch.children:
                    if x.type == "identifier":
                        name_n = x
                        break
            name = _txt(source, name_n) if name_n else "arg"
            ta = _find_named_child(ch, "type_annotation")
            tt = _type_annotation_text(ta, source) if ta else None
            out.append(ParamIR(name=name, type_text=tt, optional=opt, default_present=dfl))
        elif ch.type == "optional_parameter":
            name_n = _find_named_child(ch, "identifier")
            name = _txt(source, name_n) if name_n else "arg"
            ta = _find_named_child(ch, "type_annotation")
            tt = _type_annotation_text(ta, source) if ta else None
            out.append(ParamIR(name=name, type_text=tt, optional=True, default_present=True))
    return out


def _extract_field(pub_field: Node, source: bytes) -> FieldIR | None:
    acc = ""
    for ch in pub_field.children:
        if ch.type == "accessibility_modifier":
            inner = _find_named_child(ch, "public", "private", "protected")
            acc = _txt(source, inner) if inner else _txt(source, ch)
            break
    pid = _find_named_child(pub_field, "property_identifier")
    if pid is None:
        return None
    name = _txt(source, pid)
    ta = _find_named_child(pub_field, "type_annotation")
    tt = _type_annotation_text(ta, source) if ta else None
    return FieldIR(name=name, type_text=tt, access=acc or "public")


def _extract_method(method_node: Node, source: bytes) -> MethodIR | None:
    name = _method_name(method_node, source)
    if not name:
        return None
    body = _find_named_child(method_node, "statement_block")
    if body is None:
        return None
    text = source[body.start_byte : body.end_byte].decode()
    fp = _find_named_child(method_node, "formal_parameters")
    params = _extract_params(fp, source)
    ta = None
    for ch in method_node.children:
        if ch.type == "type_annotation" and ta is None:
            # method return type (first type_annotation after params)
            ta = ch
            break
    # May pick wrong if formal_parameters contains nested annotations; prefer annotation after )
    ret_text: str | None = None
    seen_params = False
    for ch in method_node.children:
        if ch.type == "formal_parameters":
            seen_params = True
            continue
        if seen_params and ch.type == "type_annotation":
            ret_text = _type_annotation_text(ch, source)
            break
    acc = _accessibility(method_node, source)
    return MethodIR(
        name=name,
        body_text=text,
        params=params,
        return_type_text=ret_text,
        access=acc,
    )


def _extract_class(class_node: Node, source: bytes) -> ClassIR:
    name_node = _find_named_child(class_node, "type_identifier", "identifier")
    cname = ""
    if name_node is not None:
        cname = _txt(source, name_node)
    extends = _class_extends(class_node, source)
    mlist: list[MethodIR] = []
    flist: list[FieldIR] = []
    for ch in class_node.children:
        if ch.type != "class_body":
            continue
        for mem in ch.children:
            if mem.type == "method_definition":
                mir = _extract_method(mem, source)
                if mir:
                    mlist.append(mir)
            elif mem.type == "public_field_definition":
                fir = _extract_field(mem, source)
                if fir:
                    flist.append(fir)
    return ClassIR(name=cname, extends_name=extends, fields=flist, methods=mlist)


def _import_name_from_clause(clause: Node, source: bytes) -> str | None:
    if clause.type == "identifier":
        return _txt(source, clause)
    if clause.type == "nested_identifier":
        return _txt(source, clause)
    return None


def _extract_imports(root: Node, source: bytes) -> list[ImportIR]:
    out: list[ImportIR] = []
    for imp in _iter_types(root, {"import_statement"}):
        spec = ""
        names: list[str] = []
        for ch in imp.children:
            if ch.type == "string":
                spec = _txt(source, ch).strip("'\"")
            if ch.type == "import_clause":
                for sub in ch.children:
                    if sub.type == "named_imports":
                        for nm in sub.children:
                            if nm.type == "import_specifier":
                                id1 = _find_named_child(nm, "identifier")
                                if id1 is not None:
                                    names.append(_txt(source, id1))
                    elif sub.type == "identifier":
                        names.append(_txt(source, sub))
        if spec:
            out.append(ImportIR(module_spec=spec, names=names))
    return out


def walk_typescript(tree: Tree, source: bytes, label: str) -> FileIR:
    """Collect imports, classes, methods, and fields from a parsed TypeScript file."""
    root = tree.root_node
    classes: list[ClassIR] = []
    for cn in _iter_types(root, {"class_declaration", "abstract_class_declaration"}):
        classes.append(_extract_class(cn, source))
    imports = _extract_imports(root, source)
    return FileIR(path_name=label, classes=classes, imports=imports)


def merge_metadata(files: list[FileIR]) -> dict[str, object]:
    """Summarise IR for downstream codegen (comments / metrics)."""
    total_methods = 0
    field_count = 0
    names: list[str] = []
    for f in files:
        for c in f.classes:
            names.append(c.name)
            field_count += len(c.fields)
            total_methods += len(c.methods)
    return {
        "class_names": names,
        "total_method_count": total_methods,
        "field_count": field_count,
        "file_count": len(files),
    }
