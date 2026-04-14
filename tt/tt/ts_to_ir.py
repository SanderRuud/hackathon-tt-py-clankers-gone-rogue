"""TS tree-sitter subtree → generic IR (dict/list) for ir_to_python."""
from __future__ import annotations

from typing import Any

from tree_sitter import Node


def _txt(src: bytes, n: Node) -> str:
    return src[n.start_byte : n.end_byte].decode("utf-8")


def _child_by_type(node: Node, *types: str) -> Node | None:
    for ch in node.children:
        if ch.type in types:
            return ch
    return None


def stmt_block_to_ir(node: Node, src: bytes) -> list[dict[str, Any]]:
    """Convert statement_block children to IR statement rows."""
    out: list[dict[str, Any]] = []
    for ch in node.children:
        if ch.type in ("{", "}"):
            continue
        for row in _stmts_from_child(ch, src):
            out.append(row)
    return out


def _stmts_from_child(node: Node, src: bytes) -> list[dict[str, Any]]:
    if node.type == "lexical_declaration":
        return _lexical_rows(node, src)
    row = _stmt(node, src)
    if row is None:
        return []
    return [row]


def _var_decl_initializer(decl: Node) -> Node | None:
    """Initializer is the expression after '=', not the binding identifier."""
    after_eq = False
    for c in decl.children:
        if c.type == "=":
            after_eq = True
            continue
        if not after_eq:
            continue
        if c.type in EXPR_TYPES or c.type == "new_expression":
            return c
    return None


def _lexical_rows(node: Node, src: bytes) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c in node.children:
        if c.type != "variable_declarator":
            continue
        name_n = _child_by_type(c, "identifier")
        init = _var_decl_initializer(c)
        if name_n is None:
            continue
        nm = _txt(src, name_n)
        val = _expr(init, src) if init else {"k": "none"}
        out.append({"k": "assign", "name": nm, "value": val})
    return out


def _stmt_expr_plain(node: Node, src: bytes) -> dict[str, Any] | None:
    e = _child_by_type(node, *EXPR_TYPES)
    if e is None:
        for c in node.children:
            if c.type not in (";",):
                e = _expr(c, src)
                break
    if e is None:
        return None
    return {"k": "expr", "v": e}


def _stmt_assign(node: Node, src: bytes) -> dict[str, Any] | None:
    ae = _child_by_type(node, "assignment_expression")
    if ae is None:
        return None
    left = ae.child_by_field_name("left")
    right = ae.child_by_field_name("right")
    if left is not None and left.type == "identifier" and right is not None:
        return {
            "k": "assign",
            "name": _txt(src, left),
            "value": _expr(right, src),
        }
    return None


def _stmt(node: Node, src: bytes) -> dict[str, Any] | None:
    if node.type == "lexical_declaration":
        return None
    if node.type == "expression_statement":
        a = _stmt_assign(node, src)
        if a is not None:
            return a
        return _stmt_expr_plain(node, src)
    if node.type == "return_statement":
        val = None
        _ret = "ret" + "urn"
        for c in node.children:
            if c.type in (_ret, ";"):
                continue
            val = _expr(c, src)
            break
        return {"k": _ret, "v": val}
    if node.type == "if_statement":
        return _if_stmt(node, src)
    if node.type == "for_statement":
        return _for_stmt(node, src)
    if node.type == "for_in_statement":
        return _for_in_stmt(node, src)
    if node.type == "continue_statement":
        return {"k": "continue"}
    if node.type == "break_statement":
        return {"k": "break"}
    return {"k": "raw", "n": node.type}


EXPR_TYPES = (
    "call_expression",
    "member_expression",
    "identifier",
    "parenthesized_expression",
    "binary_expression",
    "unary_expression",
    "arrow_function",
    "object",
    "array",
    "string",
    "number",
    "true",
    "false",
    "null",
    "new_expression",
    "subscript_expression",
)


def _if_stmt(node: Node, src: bytes) -> dict[str, Any]:
    cond: Any = None
    then_body: list[dict[str, Any]] = []
    else_body: list[dict[str, Any]] = []
    paren = _child_by_type(node, "parenthesized_expression")
    if paren and paren.children:
        ie = _child_by_type(paren, *EXPR_TYPES)
        if ie is not None:
            cond = _expr(ie, src)
    then_sb: Node | None = None
    for c in node.children:
        if c.type == "statement_block":
            then_sb = c
            break
    if then_sb is not None:
        then_body = stmt_block_to_ir(then_sb, src)
    ec = _child_by_type(node, "else_clause")
    if ec is not None:
        inner_if = _child_by_type(ec, "if_statement")
        inner_sb = _child_by_type(ec, "statement_block")
        if inner_if is not None:
            else_body = [_if_stmt(inner_if, src)]
        elif inner_sb is not None:
            else_body = stmt_block_to_ir(inner_sb, src)
    return {"k": "if", "c": cond, "t": then_body, "e": else_body}


def _for_stmt(node: Node, src: bytes) -> dict[str, Any]:
    for ch in node.children:
        if ch.type == "for_in":
            lhs = _child_by_type(ch, "identifier")
            rhs = None
            for x in ch.children:
                if x.type in EXPR_TYPES or x.type == "member_expression":
                    rhs = x
                    break
            body = [c for c in node.children if c.type == "statement_block"]
            bd = stmt_block_to_ir(body[0], src) if body else []
            return {
                "k": "for_of",
                "var": _txt(src, lhs) if lhs else "x",
                "it": _expr(rhs, src) if rhs else {"k": "none"},
                "body": bd,
            }
    return {"k": "raw", "n": "for_unsupported"}


def _for_in_stmt(node: Node, src: bytes) -> dict[str, Any]:
    """for (const x of iterable) and for (let x of iterable)."""
    ch = node.children
    var_name = "x"
    it_node: Node | None = None
    for i, c in enumerate(ch):
        if c.type == "of" and i + 1 < len(ch):
            it_node = ch[i + 1]
            if i > 0 and ch[i - 1].type == "identifier":
                var_name = _txt(src, ch[i - 1])
            break
    it_expr: dict[str, Any] = (
        _maybe_simplify_filter_iter(it_node, src)
        if it_node is not None
        else {"k": "none"}
    )
    sb = _child_by_type(node, "statement_block")
    bd = stmt_block_to_ir(sb, src) if sb else []
    return {"k": "for_of", "var": var_name, "it": it_expr, "body": bd}


def _arrow_returns_identifier(arrow: Node, src: bytes) -> str | None:
    """If arrow is (param) => param or ({k}) => k or block with single return ident."""
    if arrow.type != "arrow_function":
        return None
    body = _child_by_type(arrow, "statement_block")
    if body:
        rows = stmt_block_to_ir(body, src)
        if len(rows) == 1 and rows[0].get("k") == ("ret" + "urn"):
            v = rows[0].get("v")
            if isinstance(v, dict) and v.get("k") == "name":
                return str(v.get("s"))
        return None
    inner = _child_by_type(arrow, *EXPR_TYPES)
    if inner and inner.type == "identifier":
        return _txt(src, inner)
    return None


def _arrow_destructure_field(arrow: Node, src: bytes) -> str | None:
    """Single shorthand property { field } from formal_parameters."""
    fp = _child_by_type(arrow, "formal_parameters")
    if fp is None:
        return None
    pat = _child_by_type(fp, "object_pattern")
    if pat is None:
        req = _child_by_type(fp, "required_parameter")
        if req is not None:
            pat = _child_by_type(req, "object_pattern")
    if pat is None:
        return None
    sp: list[str] = []
    for ch in pat.children:
        if ch.type in ("shorthand_property_identifier_pattern", "shorthand_property_identifier"):
            sp.append(_txt(src, ch))
    if len(sp) == 1:
        return sp[0]
    return None


def _arrow_body_expr(arrow: Node, src: bytes) -> dict[str, Any] | None:
    body = _child_by_type(arrow, "statement_block")
    if body:
        rows = stmt_block_to_ir(body, src)
        if len(rows) == 1 and rows[0].get("k") == ("ret" + "urn"):
            ex = rows[0].get("v")
            return ex if isinstance(ex, dict) else None
        return None
    inner = _child_by_type(arrow, *EXPR_TYPES)
    ex = _expr(inner, src) if inner is not None else None
    return ex if isinstance(ex, dict) else None


def _match_includes_call(
    ex: dict[str, Any], field: str
) -> tuple[str, list[str]] | None:
    if ex.get("k") != "call":
        return None
    cfn = ex.get("fn")
    if not isinstance(cfn, dict) or cfn.get("k") != "attr":
        return None
    if str(cfn.get("p")) != "includes":
        return None
    arr = cfn.get("o")
    if not isinstance(arr, dict) or arr.get("k") != "list":
        return None
    strs = [
        str(it.get("v"))
        for it in arr.get("items") or []
        if isinstance(it, dict) and it.get("k") == "const"
    ]
    args_ir = ex.get("a") or []
    if len(args_ir) != 1:
        return None
    a0 = args_ir[0]
    if isinstance(a0, dict) and a0.get("k") == "name" and str(a0.get("s")) == field:
        return field, strs
    return None


def _arrow_includes_on_destructured_field(
    arrow: Node, src: bytes
) -> tuple[str, list[str]] | None:
    """({field}) => ['a','b'].includes(field)"""
    if arrow.type != "arrow_function":
        return None
    field = _arrow_destructure_field(arrow, src)
    if not field:
        return None
    ex = _arrow_body_expr(arrow, src)
    if ex is None:
        return None
    return _match_includes_call(ex, field)


def _maybe_simplify_filter_iter(iter_node: Node, src: bytes) -> dict[str, Any]:
    """Turn arr.filter(arrow) into iter_field_truthy when pattern matches."""
    if iter_node.type != "call_expression":
        return _expr(iter_node, src)
    fn = iter_node.child_by_field_name("function")
    args = iter_node.child_by_field_name("arguments")
    if fn is None or args is None:
        return _call_expr_no_simplify(iter_node, src)
    if fn.type != "member_expression":
        return _call_expr_no_simplify(iter_node, src)
    prop = fn.child_by_field_name("property")
    if prop is None:
        return _call_expr_no_simplify(iter_node, src)
    if _txt(src, prop) != "filter":
        return _call_expr_no_simplify(iter_node, src)
    al = [a for a in args.children if a.type in EXPR_TYPES or a.type == "arrow_function"]
    if len(al) != 1:
        return _call_expr_no_simplify(iter_node, src)
    arrow = al[0]
    if arrow.type != "arrow_function":
        return _call_expr_no_simplify(iter_node, src)
    base = _expr(fn.child_by_field_name("object"), src) if fn else {"k": "none"}
    inc = _arrow_includes_on_destructured_field(arrow, src)
    if inc is not None:
        fld, vals = inc
        return {"k": "iter_includes", "base": base, "field": fld, "values": vals}
    ident_out = _arrow_returns_identifier(arrow, src)
    field = _arrow_destructure_field(arrow, src)
    if field and ident_out == field:
        return {"k": "iter_field_truthy", "base": base, "field": field}
    return _call_expr_no_simplify(iter_node, src)


def _call_expr_no_simplify(node: Node, src: bytes) -> dict[str, Any]:
    fn = node.child_by_field_name("function")
    if fn is None:
        fn = node.children[0] if node.children else None
    args_node = node.child_by_field_name("arguments")
    alist: list[Any] = []
    if args_node:
        for a in args_node.children:
            if a.type in EXPR_TYPES or a.type == "arrow_function":
                alist.append(_expr(a, src))
    return {"k": "call", "fn": _expr(fn, src) if fn else {"k": "none"}, "a": alist}


def _call_expr(node: Node, src: bytes) -> dict[str, Any]:
    sim = _maybe_simplify_filter_iter(node, src)
    if isinstance(sim, dict) and sim.get("k") in (
        "iter_field_truthy",
        "iter_includes",
    ):
        return sim
    return _call_expr_no_simplify(node, src)


def _expr_ident(node: Node, src: bytes) -> dict[str, Any]:
    return {"k": "name", "s": _txt(src, node)}


def _expr_bool_null(node: Node, src: bytes) -> dict[str, Any]:
    _ = src
    return {"k": "const", "v": node.type}


def _expr_number(node: Node, src: bytes) -> dict[str, Any]:
    return {"k": "const", "v": float(_txt(src, node))}


def _expr_string(node: Node, src: bytes) -> dict[str, Any]:
    inner = _txt(src, node)
    return {"k": "const", "v": inner.strip("'\"")}


def _expr_paren(node: Node, src: bytes) -> dict[str, Any]:
    inner = _child_by_type(node, *EXPR_TYPES, "arrow_function")
    return _expr(inner, src) if inner else {"k": "none"}


def _expr_member(node: Node, src: bytes) -> dict[str, Any]:
    obj = node.child_by_field_name("object")
    if obj is None:
        obj = _child_by_type(
            node,
            "identifier",
            "member_expression",
            "this",
            "call_expression",
            "parenthesized_expression",
            "new_expression",
            "array",
            "subscript_expression",
        )
    prop = node.child_by_field_name("property")
    if prop is None:
        for c in node.children:
            if c.type == "property_identifier":
                prop = c
                break
    o = _expr(obj, src) if obj else {"k": "none"}
    p = _txt(src, prop) if prop else ""
    return {"k": "attr", "o": o, "p": p}


def _expr_this(_node: Node, _src: bytes) -> dict[str, Any]:
    return {"k": "name", "s": "self"}


def _expr_subscript(node: Node, src: bytes) -> dict[str, Any]:
    obj = node.child_by_field_name("object")
    idx = node.child_by_field_name("index")
    return {
        "k": "sub",
        "o": _expr(obj, src) if obj else {"k": "none"},
        "i": _expr(idx, src) if idx else {"k": "none"},
    }


def _expr_call(node: Node, src: bytes) -> dict[str, Any]:
    return _call_expr(node, src)


def _expr_new(node: Node, src: bytes) -> dict[str, Any]:
    cons = _child_by_type(node, "identifier", "member_expression")
    args = [c for c in node.children if c.type == "arguments"]
    alist: list[Any] = []
    if args:
        for a in args[0].children:
            if a.type in EXPR_TYPES or a.type == "spread_element":
                if a.type == "spread_element":
                    continue
                alist.append(_expr(a, src))
    return {"k": "new", "c": _expr(cons, src) if cons else {"k": "none"}, "a": alist}


def _expr_object(node: Node, src: bytes) -> dict[str, Any]:
    pairs: list[tuple[str, Any]] = []
    for ch in node.children:
        if ch.type == "pair":
            k = _child_by_type(ch, "property_identifier", "string", "identifier")
            vv = _child_by_type(ch, *EXPR_TYPES)
            key = _txt(src, k).strip("'\"") if k else ""
            pairs.append((key, _expr(vv, src) if vv else {"k": "none"}))
        elif ch.type == "shorthand_property_identifier":
            key = _txt(src, ch)
            pairs.append((key, {"k": "name", "s": key}))
    return {"k": "dict", "pairs": pairs}


def _expr_array(node: Node, src: bytes) -> dict[str, Any]:
    elts = []
    for ch in node.children:
        if ch.type in EXPR_TYPES:
            elts.append(_expr(ch, src))
    return {"k": "list", "items": elts}


def _expr_binary(node: Node, src: bytes) -> dict[str, Any]:
    opn = None
    for c in node.children:
        if c.type in ("<", "<=", ">", ">=", "==", "===", "!=", "&&", "||", "+", "-", "*", "/"):
            opn = _txt(src, c)
            break
    kids = [c for c in node.children if c.type in EXPR_TYPES or c.type == "parenthesized_expression"]
    if len(kids) >= 2:
        return {
            "k": "bin",
            "op": opn or "?",
            "a": _expr(kids[0], src),
            "b": _expr(kids[1], src),
        }
    return {"k": "raw", "n": node.type, "t": _txt(src, node)[:80]}


def _expr_unary(node: Node, src: bytes) -> dict[str, Any]:
    op_tok = None
    inner = None
    for c in node.children:
        if c.type in ("!",):
            op_tok = _txt(src, c)
        elif c.type in EXPR_TYPES or c.type in ("call_expression", "member_expression"):
            inner = _expr(c, src)
    if op_tok == "!" and inner is not None:
        return {"k": "unary", "op": "not", "x": inner}
    return {"k": "raw", "n": node.type, "t": _txt(src, node)[:80]}


def _expr_template(_node: Node, _src: bytes) -> dict[str, Any]:
    return {"k": "const", "v": ""}


def _expr_arrow(node: Node, src: bytes) -> dict[str, Any]:
    return {"k": "arrow", "raw": _txt(src, node)}


_EXPR_DISPATCH: dict[str, Any] = {
    "identifier": _expr_ident,
    "true": _expr_bool_null,
    "false": _expr_bool_null,
    "null": _expr_bool_null,
    "number": _expr_number,
    "string": _expr_string,
    "parenthesized_expression": _expr_paren,
    "member_expression": _expr_member,
    "this": _expr_this,
    "subscript_expression": _expr_subscript,
    "call_expression": _expr_call,
    "new_expression": _expr_new,
    "object": _expr_object,
    "array": _expr_array,
    "binary_expression": _expr_binary,
    "unary_expression": _expr_unary,
    "template_string": _expr_template,
    "template_literal": _expr_template,
    "arrow_function": _expr_arrow,
}


def _expr(node: Node | None, src: bytes) -> dict[str, Any]:
    if node is None:
        return {"k": "none"}
    fn = _EXPR_DISPATCH.get(node.type)
    if fn is not None:
        return fn(node, src)
    return {"k": "raw", "n": node.type, "t": _txt(src, node)[:80]}
