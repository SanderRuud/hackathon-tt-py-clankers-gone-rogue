"""Helpers to turn ``ClassIR`` / ``MethodIR`` into Python ``params_src`` strings for body translation."""
from __future__ import annotations

from tt.ast_walker import ClassIR, FileIR, MethodIR
from tt.mappings import camel_to_snake


def find_target_class(files: list[FileIR], class_name: str) -> ClassIR | None:
    """First ``ClassIR`` named ``class_name`` across parsed files."""
    for f in files:
        for c in f.classes:
            if c.name == class_name:
                return c
    return None


def method_by_ts_name(class_ir: ClassIR, ts_name: str) -> MethodIR | None:
    for m in class_ir.methods:
        if m.name == ts_name:
            return m
    return None


def ts_type_to_python_annotation(ts_type: str | None) -> str | None:
    """Minimal ``string`` / ``number`` / ``boolean`` / ``void`` mapping."""
    if not ts_type:
        return None
    t = ts_type.strip()
    if t in ("string", "str"):
        return "str"
    if t in ("number", "float"):
        return "float"
    if t in ("boolean", "bool"):
        return "bool"
    if t in ("void",):
        return "None"
    if t.endswith("[]"):
        inner = ts_type[:-2].strip()
        inn = ts_type_to_python_annotation(inner)
        if inn:
            return f"list[{inn}]"
        return "list"
    return None


def build_params_src(method: MethodIR, *, include_self: bool = True, use_annotations: bool = True) -> str:
    """Build ``(self, a: str, ...)`` string compatible with :func:`body_translate.translate_method_body`."""
    parts: list[str] = []
    if include_self:
        parts.append("self")
    for p in method.params:
        ann = ""
        if use_annotations and p.type_text:
            py_t = ts_type_to_python_annotation(p.type_text)
            if py_t:
                ann = f": {py_t}"
        if p.optional and p.default_present:
            parts.append(f"{p.name}{ann} = None")
        else:
            parts.append(f"{p.name}{ann}")
    inner = ", ".join(parts)
    return f"({inner})"


def public_python_name(ts_method_name: str) -> str:
    """``getPerformance`` → ``get_performance`` for emitted Python ``def`` names."""
    return camel_to_snake(ts_method_name)
