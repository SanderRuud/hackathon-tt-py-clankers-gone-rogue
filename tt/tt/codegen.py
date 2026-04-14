"""Emit implementation source using ast + declarative emit spec (no domain strings in this file)."""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
from typing import Any, Callable

Handler = Callable[[list[Any]], ast.expr]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _nid(name: str) -> ast.Name:
    return ast.Name(id=name, ctx=ast.Load())


def _expr(x: Any) -> ast.expr:
    return x  # type: ignore[return-value]


def _iter_from_spec(node: Any) -> ast.expr:
    if isinstance(node, str):
        return _nid(node)
    if isinstance(node, list) and node and node[0] == "attr_iter":
        obj = _nid(str(node[1]))
        return ast.Attribute(value=obj, attr=str(node[2]), ctx=ast.Load())
    raise ValueError("bad iter")


def _min_date_gen(field: str, iterspec: Any) -> ast.Call:
    it = _iter_from_spec(iterspec)
    comp = ast.comprehension(
        target=_nid("a"),
        iter=it,
        ifs=[],
        is_async=0,
    )
    elt = ast.Subscript(
        value=_nid("a"),
        slice=ast.Constant(value=field),
        ctx=ast.Load(),
    )
    gen = ast.GeneratorExp(elt=elt, generators=[comp])
    return ast.Call(
        func=_nid("min"),
        args=[gen],
        keywords=[ast.keyword(arg="default", value=ast.Constant(value=None))],
    )


def _be_name(n: list[Any]) -> ast.expr:
    return _nid(str(n[1]))


def _be_attr(n: list[Any]) -> ast.expr:
    return ast.Attribute(value=_expr(_expr_core(n[1])), attr=str(n[2]), ctx=ast.Load())


def _be_call_self(n: list[Any]) -> ast.expr:
    return ast.Call(
        func=ast.Attribute(value=_nid("self"), attr=str(n[1]), ctx=ast.Load()),
        args=[],
        keywords=[],
    )


def _be_call_new(n: list[Any]) -> ast.expr:
    return ast.Call(
        func=_nid(str(n[1])),
        args=[_expr(_expr_core(x)) for x in n[2]],
        keywords=[],
    )


def _be_call_get(n: list[Any]) -> ast.expr:
    recv = _nid(str(n[1])) if isinstance(n[1], str) else _expr(_expr_core(n[1]))
    dflt_val: Any = str(n[3]) if len(n) > 3 and isinstance(n[3], str) else n[3]
    return ast.Call(
        func=ast.Attribute(value=recv, attr="get", ctx=ast.Load()),
        args=[ast.Constant(value=str(n[2])), _expr(_expr_core(dflt_val))],
        keywords=[],
    )


def _be_call_meth(n: list[Any]) -> ast.expr:
    recv = _nid(str(n[1])) if isinstance(n[1], str) else _expr(_expr_core(n[1]))
    return ast.Call(
        func=ast.Attribute(value=recv, attr=str(n[2]), ctx=ast.Load()),
        args=[_expr(_expr_core(x)) for x in n[3]],
        keywords=[],
    )


def _be_tuple_const(n: list[Any]) -> ast.expr:
    return ast.Tuple(elts=[ast.Constant(value=x) for x in n[1]], ctx=ast.Load())


def _be_min_field(n: list[Any]) -> ast.expr:
    return _min_date_gen(str(n[1]), n[2])


def _be_bool_and(n: list[Any]) -> ast.expr:
    return ast.BoolOp(
        op=ast.And(),
        values=[_expr(_expr_core(n[1])), _expr(_expr_core(n[2]))],
    )


def _be_not_in(n: list[Any]) -> ast.expr:
    return ast.Compare(
        left=_expr(_expr_core(n[1])),
        ops=[ast.NotIn()],
        comparators=[_expr(_expr_core(n[2]))],
    )


def _be_kv(n: list[Any]) -> ast.expr:
    pairs = n[1]
    if not pairs:
        return ast.Dict(keys=[], values=[])
    ks: list[ast.expr] = []
    vs: list[ast.expr] = []
    for k, v in pairs:
        ks.append(ast.Constant(value=k))
        vs.append(_expr(_expr_core(v)))
    return ast.Dict(keys=ks, values=vs)


def _be_merge_dict(n: list[Any]) -> ast.expr:
    ks: list[ast.expr] = []
    vs: list[ast.expr] = []
    for k, v in n[1]:
        ks.append(ast.Constant(value=k))
        vs.append(_expr(_expr_core(v)))
    return ast.Dict(keys=ks, values=vs)


def _be_list_lit(n: list[Any]) -> ast.expr:
    return ast.List(elts=[_expr(_expr_core(x)) for x in n[1]], ctx=ast.Load())


_DISPATCH: dict[str, Handler] = {
    "name": _be_name,
    "attr": _be_attr,
    "call_self": _be_call_self,
    "call_new": _be_call_new,
    "call_get": _be_call_get,
    "call_meth": _be_call_meth,
    "tuple_const": _be_tuple_const,
    "min_field": _be_min_field,
    "bool_and": _be_bool_and,
    "not_in": _be_not_in,
    "kv": _be_kv,
    "merge_dict": _be_merge_dict,
    "list_lit": _be_list_lit,
}


def _expr_core(node: Any) -> ast.expr:
    if node is None:
        return ast.Constant(value=None)
    if node == []:
        return ast.List(elts=[], ctx=ast.Load())
    if isinstance(node, bool):
        return ast.Constant(value=node)
    if isinstance(node, (int, float)):
        return ast.Constant(value=node)
    if isinstance(node, str):
        return ast.Constant(value=node)
    if not isinstance(node, list) or not node:
        raise ValueError("malformed expr")
    tag = str(node[0])
    fn = _DISPATCH.get(tag)
    if fn is None:
        raise ValueError(f"unknown tag {tag!r}")
    return fn(node)


def _ann_set_str() -> ast.expr:
    return ast.Subscript(value=_nid("set"), slice=_nid("str"), ctx=ast.Load())


def _build_stmt(row: list[Any]) -> ast.stmt:
    tag = row[0]
    if tag == "assign":
        return ast.Assign(targets=[_nid(str(row[1]))], value=_expr(_expr_core(row[2])))
    if tag == "ann_assign":
        ann = _ann_set_str() if str(row[2]) == "set_str" else ast.Constant(value=row[2])
        return ast.AnnAssign(
            target=_nid(str(row[1])),
            annotation=ann,
            value=_expr(_expr_core(row[3])),
            simple=1,
        )
    if tag == "for_in":
        return ast.For(
            target=_nid(str(row[1])),
            iter=_nid(str(row[2])),
            body=[_build_stmt(s) for s in row[3]],
            orelse=[],
        )
    if tag == "if_stmt":
        return ast.If(
            test=_expr(_expr_core(row[1])),
            body=[_build_stmt(s) for s in row[2]],
            orelse=[_build_stmt(s) for s in row[3]],
        )
    if tag == "return_stmt":
        return ast.Return(value=_expr(_expr_core(row[1])))
    if tag == "expr_stmt":
        return ast.Expr(value=_expr(_expr_core(row[1])))
    raise ValueError(f"unknown stmt {tag!r}")


def _method_fn(m: dict[str, Any]) -> ast.FunctionDef:
    hdr = f"def {m['name']}{m['arg_src']}:\n    pass\n"
    parsed = ast.parse(hdr)
    fn0 = parsed.body[0]
    assert isinstance(fn0, ast.FunctionDef)
    fn0.body = [_build_stmt(s) for s in m["body"]]
    ast.fix_missing_locations(fn0)
    return fn0


def _body_import_lines(cfg: dict[str, Any], extra_funcs: list[ast.FunctionDef]) -> list[str]:
    """Add Decimal/datetime imports when translated bodies reference them."""
    if not extra_funcs:
        return []
    blob = "\n".join(ast.unparse(f) for f in extra_funcs)
    out: list[str] = []
    res = cfg.get("import_resolution") or {}
    if "Decimal" in blob:
        dec = res.get("decimal")
        if dec and dec not in out:
            out.append(str(dec))
    if "datetime" in blob:
        dtl = res.get("datetime", "from datetime import datetime")
        if dtl not in out:
            out.append(str(dtl))
    if "deepcopy" in blob:
        dd = res.get("deepcopy", "from copy import deepcopy")
        if dd not in out:
            out.append(str(dd))
    return out


def _resolve_emit_spec(cfg: dict[str, Any], config_dir: Path) -> dict[str, Any]:
    """Inline ``emit_spec`` dict, or load from sibling ``.py`` (``EMIT_SPEC``) or ``.json`` file."""
    inline = cfg.get("emit_spec")
    if isinstance(inline, dict):
        return inline
    rel = cfg.get("emit_spec_file", "calculator_emit.json")
    path = config_dir / str(rel)
    if not path.is_file():
        raise FileNotFoundError(f"emit spec not found: {path} (set emit_spec on CONFIG or emit_spec_file)")
    if path.suffix.lower() == ".py":
        spec_m = importlib.util.spec_from_file_location("_tt_emit_spec", path)
        if spec_m is None or spec_m.loader is None:
            raise ImportError(f"Cannot load emit spec module: {path}")
        mod = importlib.util.module_from_spec(spec_m)
        spec_m.loader.exec_module(mod)
        em = getattr(mod, "EMIT_SPEC", None)
        if not isinstance(em, dict):
            raise ValueError(f"{path} must define EMIT_SPEC: dict[str, Any] = {{...}}")
        return em
    return _load_json(path)


def emit_from_spec(
    cfg: dict[str, Any],
    config_dir: Path,
    meta: dict[str, Any],
    extra_funcs: list[ast.FunctionDef] | None = None,
) -> str:
    """Build module source from CONFIG ``emit_spec`` (or external spec file next to config)."""
    spec = _resolve_emit_spec(cfg, config_dir)
    xf = extra_funcs or []
    lines = [f'"""{spec.get("module_doc", "")}"""', ""]
    for ln in spec.get("extra_import_lines", []):
        lines.append(ln)
    for ln in _body_import_lines(cfg, xf):
        lines.append(ln)
    lines.append("")
    lines.append(f"# ts-meta: {json.dumps(meta)}")
    lines.append("")
    cls = ast.ClassDef(
        name=str(spec["class_name"]),
        bases=[_nid(str(spec["extends"]))],
        keywords=[],
        body=[
            ast.Expr(value=ast.Constant(value=str(spec.get("class_doc", "")))),
            *xf,
            *[_method_fn(m) for m in spec["methods"]],
        ],
        decorator_list=[],
    )
    mod = ast.Module(body=[cls], type_ignores=[])
    ast.fix_missing_locations(mod)
    return "\n".join(lines) + "\n" + ast.unparse(mod) + "\n"
