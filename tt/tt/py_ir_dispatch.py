"""IR expr -> Python ast: one small handler per kind (keeps ir_to_python.py slim)."""
from __future__ import annotations

import ast
from typing import Any, Callable

from tt.ir_to_python import Xcfg, _nid, _py_call, _py_expr

_Handler = Callable[[dict[str, Any], Xcfg], ast.expr]


def _k_const(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    _ = cfg
    v = e.get("v")
    if v == "true":
        return ast.Constant(value=True)
    if v == "false":
        return ast.Constant(value=False)
    if v == "null":
        return ast.Constant(value=None)
    return ast.Constant(value=v)


def _k_name(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    _ = cfg
    return _nid(str(e.get("s", "x")))


def _k_attr(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    _ = cfg
    base = _py_expr(e.get("o"), cfg)
    prop = str(e.get("p", ""))
    if prop == "length":
        return ast.Call(func=_nid("len"), args=[base], keywords=[])
    return ast.Attribute(value=base, attr=prop, ctx=ast.Load())


def _k_sub(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    return ast.Subscript(
        value=_py_expr(e.get("o"), cfg),
        slice=_py_expr(e.get("i"), cfg),
        ctx=ast.Load(),
    )


def _k_call(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    return _py_call(e, cfg)


def _k_new(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    c = e.get("c", {})
    args = [_py_expr(a, cfg) for a in e.get("a", [])]
    fn = _py_expr(c, cfg)
    if isinstance(fn, ast.Name) and fn.id.lower() == "big":
        return ast.Call(func=_nid(cfg.decimal_name), args=args, keywords=[])
    if isinstance(fn, ast.Name) and fn.id == "Date":
        return ast.Call(
            func=ast.Attribute(value=_nid("datetime"), attr="now", ctx=ast.Load()),
            args=[],
            keywords=[],
        )
    return ast.Call(func=fn, args=args, keywords=[])


def _k_iter_field_truthy(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    base_e = _py_expr(e.get("base"), cfg)
    fld = str(e.get("field", ""))
    item = _nid("item")
    return ast.ListComp(
        elt=item,
        generators=[
            ast.comprehension(
                target=item,
                iter=base_e,
                ifs=[
                    ast.Subscript(
                        value=item,
                        slice=ast.Constant(value=fld),
                        ctx=ast.Load(),
                    )
                ],
                is_async=0,
            )
        ],
    )


def _k_iter_includes(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    base_e = _py_expr(e.get("base"), cfg)
    fld = str(e.get("field", ""))
    vals = list(e.get("values") or [])
    item = _nid("item")
    tup = ast.Tuple(
        elts=[ast.Constant(value=v) for v in vals],
        ctx=ast.Load(),
    )
    test = ast.Compare(
        left=ast.Subscript(
            value=item,
            slice=ast.Constant(value=fld),
            ctx=ast.Load(),
        ),
        ops=[ast.In()],
        comparators=[tup],
    )
    return ast.ListComp(
        elt=item,
        generators=[ast.comprehension(target=item, iter=base_e, ifs=[test], is_async=0)],
    )


def _k_dict(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    ks: list[ast.expr] = []
    vs: list[ast.expr] = []
    for key, val in e.get("pairs", []):
        ks.append(ast.Constant(value=key))
        vs.append(_py_expr(val, cfg))
    return ast.Dict(keys=ks, values=vs)


def _k_list(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    return ast.List(elts=[_py_expr(i, cfg) for i in e.get("items", [])], ctx=ast.Load())


def _k_unary(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    inner = _py_expr(e.get("x"), cfg)
    if str(e.get("op")) == "not":
        return ast.UnaryOp(op=ast.Not(), operand=inner)
    return inner


def _k_bin(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    op = str(e.get("op", ""))
    a = _py_expr(e.get("a"), cfg)
    b = _py_expr(e.get("b"), cfg)
    if op == "&&":
        return ast.BoolOp(op=ast.And(), values=[a, b])
    if op == "||":
        return ast.BoolOp(op=ast.Or(), values=[a, b])
    op_map = {
        "+": ast.Add(),
        "-": ast.Sub(),
        "*": ast.Mult(),
        "/": ast.Div(),
        "==": ast.Eq(),
        "===": ast.Eq(),
        "!=": ast.NotEq(),
        "<": ast.Lt(),
        ">": ast.Gt(),
        "<=": ast.LtE(),
        ">=": ast.GtE(),
    }
    if op in op_map:
        if op in ("==", "===", "!=", "<", ">", "<=", ">="):
            return ast.Compare(left=a, ops=[op_map[op]], comparators=[b])
        return ast.BinOp(left=a, op=op_map[op], right=b)
    return ast.BinOp(left=a, op=ast.Add(), right=b)


def _k_raw(_e: dict[str, Any], _cfg: Xcfg) -> ast.expr:
    return ast.Constant(value=None)


EXPR_HANDLERS: dict[str, _Handler] = {
    "const": _k_const,
    "name": _k_name,
    "attr": _k_attr,
    "sub": _k_sub,
    "call": _k_call,
    "new": _k_new,
    "iter_field_truthy": _k_iter_field_truthy,
    "iter_includes": _k_iter_includes,
    "dict": _k_dict,
    "list": _k_list,
    "unary": _k_unary,
    "bin": _k_bin,
    "raw": _k_raw,
}
