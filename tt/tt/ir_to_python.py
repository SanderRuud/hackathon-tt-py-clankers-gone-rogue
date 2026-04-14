"""Generic IR (from ts_to_ir) → Python ast."""
from __future__ import annotations

import ast
from typing import Any, Callable

ExprHandler = Callable[[dict[str, Any], "Xcfg"], ast.expr]


def _nid(name: str) -> ast.Name:
    return ast.Name(id=name, ctx=ast.Load())


def _stmt_list(
    rows: list[dict[str, Any]],
    x: Any,
) -> list[ast.stmt]:
    out: list[ast.stmt] = []
    for row in rows:
        s = _stmt_one(row, x)
        if s is not None:
            out.append(s)
    return out


def _stmt_one(row: dict[str, Any], x: Any) -> ast.stmt | None:
    k = row.get("k")
    if k == "assign":
        py_nm = str(row.get("name", "x"))
        return ast.Assign(
            targets=[_nid(py_nm)],
            value=_py_expr(row.get("value"), x),
        )
    if k == "return":
        return ast.Return(value=_py_expr(row.get("v"), x))
    if k == "expr":
        ev = _py_expr(row.get("v"), x)
        if isinstance(ev, ast.Constant) and ev.value is None:
            return None
        return ast.Expr(value=ev)
    if k == "if":
        tb = _stmt_list(row.get("t") or [], x)
        if not tb:
            tb = [ast.Pass()]
        return ast.If(
            test=_py_expr(row.get("c"), x),
            body=tb,
            orelse=_stmt_list(row.get("e") or [], x),
        )
    if k == "for_of":
        fb = _stmt_list(row.get("body") or [], x)
        if not fb:
            fb = [ast.Pass()]
        return ast.For(
            target=_nid(str(row.get("var", "x"))),
            iter=_py_expr(row.get("it"), x),
            body=fb,
            orelse=[],
        )
    if k == "continue":
        return ast.Continue()
    if k == "break":
        return ast.Break()
    return ast.Expr(value=ast.Constant(value=f"<unsupported:{k}>"))


class Xcfg:
    def __init__(self, decimal_name: str = "Decimal") -> None:
        self.decimal_name = decimal_name


def _py_attr_call(recv: ast.expr, meth: str, args: list[ast.expr]) -> ast.expr | None:
    if meth in ("plus", "minus", "times", "div"):
        op_cls: type[ast.operator] | None = {
            "plus": ast.Add,
            "minus": ast.Sub,
            "times": ast.Mult,
            "div": ast.Div,
        }.get(meth)
        if op_cls and len(args) == 1:
            return ast.BinOp(left=recv, op=op_cls(), right=args[0])
    if isinstance(recv, ast.Name) and recv.id == "Logger" and meth == "warn":
        return ast.Constant(value=None)
    if meth == "eq" and len(args) == 1:
        return ast.Compare(left=recv, ops=[ast.Eq()], comparators=[args[0]])
    if meth == "includes" and len(args) == 1:
        return ast.Compare(left=args[0], ops=[ast.In()], comparators=[recv])
    return None


def _py_call(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    fn = e.get("fn", {})
    args = [_py_expr(a, cfg) for a in e.get("a", [])]
    if isinstance(fn, dict) and fn.get("k") == "name" and str(fn.get("s")) == "cloneDeep":
        return ast.Call(func=_nid("deepcopy"), args=args, keywords=[])
    if isinstance(fn, dict) and fn.get("k") == "attr":
        recv = _py_expr(fn.get("o"), cfg)
        meth = str(fn.get("p", ""))
        alt = _py_attr_call(recv, meth, args)
        if alt is not None:
            return alt
        return ast.Call(
            func=ast.Attribute(value=recv, attr=meth, ctx=ast.Load()),
            args=args,
            keywords=[],
        )
    fn_e = _py_expr(fn, cfg) if isinstance(fn, dict) else ast.Constant(value=None)
    return ast.Call(func=fn_e, args=args, keywords=[])


def _const_val(e: dict[str, Any]) -> ast.expr:
    v = e.get("v")
    if v == "true":
        return ast.Constant(value=True)
    if v == "false":
        return ast.Constant(value=False)
    if v == "null":
        return ast.Constant(value=None)
    return ast.Constant(value=v)


def _ex_const(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    _ = cfg
    return _const_val(e)


def _ex_name(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    _ = cfg
    return _nid(str(e.get("s", "x")))


def _ex_attr(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    base = _py_expr(e.get("o"), cfg)
    prop = str(e.get("p", ""))
    if prop == "length":
        return ast.Call(func=_nid("len"), args=[base], keywords=[])
    return ast.Attribute(value=base, attr=prop, ctx=ast.Load())


def _ex_sub(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    return ast.Subscript(
        value=_py_expr(e.get("o"), cfg),
        slice=_py_expr(e.get("i"), cfg),
        ctx=ast.Load(),
    )


def _ex_call(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    return _py_call(e, cfg)


def _ex_new(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
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


def _ex_iter_field_truthy(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
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


def _ex_iter_includes(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
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
        generators=[
            ast.comprehension(
                target=item,
                iter=base_e,
                ifs=[test],
                is_async=0,
            )
        ],
    )


def _ex_dict(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    ks: list[ast.expr] = []
    vs: list[ast.expr] = []
    for key, val in e.get("pairs", []):
        ks.append(ast.Constant(value=key))
        vs.append(_py_expr(val, cfg))
    return ast.Dict(keys=ks, values=vs)


def _ex_list(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    return ast.List(elts=[_py_expr(i, cfg) for i in e.get("items", [])], ctx=ast.Load())


def _ex_unary(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
    inner = _py_expr(e.get("x"), cfg)
    if str(e.get("op")) == "not":
        return ast.UnaryOp(op=ast.Not(), operand=inner)
    return inner


def _ex_bin(e: dict[str, Any], cfg: Xcfg) -> ast.expr:
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


def _ex_raw(_e: dict[str, Any], _cfg: Xcfg) -> ast.expr:
    return ast.Constant(value=None)


_EXPR: dict[str, ExprHandler] = {
    "const": _ex_const,
    "name": _ex_name,
    "attr": _ex_attr,
    "sub": _ex_sub,
    "call": _ex_call,
    "new": _ex_new,
    "iter_field_truthy": _ex_iter_field_truthy,
    "iter_includes": _ex_iter_includes,
    "dict": _ex_dict,
    "list": _ex_list,
    "unary": _ex_unary,
    "bin": _ex_bin,
    "raw": _ex_raw,
}


def _py_expr(e: Any, cfg: Xcfg) -> ast.expr:
    if e is None or (isinstance(e, dict) and e.get("k") == "none"):
        return ast.Constant(value=None)
    if not isinstance(e, dict):
        return ast.Constant(value=None)
    key = str(e.get("k", ""))
    fn = _EXPR.get(key)
    if fn is not None:
        return fn(e, cfg)
    return ast.Constant(value=None)


def patch_member_enum(e: dict[str, Any]) -> dict[str, Any]:
    """Rewrite Enum.VALUE style attrs to const string for return optimization."""
    if not isinstance(e, dict):
        return e
    if e.get("k") == "attr":
        inner = e.get("o")
        if isinstance(inner, dict) and inner.get("k") == "name":
            root = str(inner.get("s", ""))
            leaf = str(e.get("p", ""))
            if root.endswith("Type"):
                return {"k": "const", "v": leaf}
    return e


def ir_to_function_def(
    name_py: str,
    params: ast.arguments,
    stmts_ir: list[dict[str, Any]],
    cfg: Xcfg | None = None,
) -> ast.FunctionDef:
    x = cfg or Xcfg()
    body = _stmt_list(stmts_ir, x)
    if not body:
        body = [ast.Pass()]
    return ast.FunctionDef(
        name=name_py,
        args=params,
        body=body,
        decorator_list=[],
        returns=None,
        lineno=0,
    )


def rewrite_returns_enum_strings(stmts: list[dict[str, Any]]) -> None:
    for s in stmts:
        if isinstance(s, dict) and s.get("k") == "return":
            v = s.get("v")
            if isinstance(v, dict):
                s["v"] = patch_member_enum(v)
