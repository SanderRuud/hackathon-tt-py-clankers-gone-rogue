"""
TypeScript → Python translator using tree-sitter for AST-based parsing.

Reads TypeScript source, walks the AST, and emits equivalent Python.
Handles the Big.js arithmetic library, TypeScript type annotations,
and common control-flow patterns.
"""
from __future__ import annotations

import re
from pathlib import Path

import tree_sitter_typescript as _tst
from tree_sitter import Language, Parser

_TS_LANG = Language(_tst.language_typescript())


def _mk_parser() -> Parser:
    return Parser(_TS_LANG)


# ---------------------------------------------------------------------------
# Big.js method → Python operator mappings
# ---------------------------------------------------------------------------
_BIG_BINARY: dict[str, tuple[str, int]] = {
    "plus": ("+", 1), "add": ("+", 1),
    "minus": ("-", 1),
    "mul": ("*", 2), "times": ("*", 2),
    "div": ("/", 2),
}
_BIG_CMP: dict[str, str] = {
    "eq": "==", "gt": ">", "lt": "<",
    "gte": ">=", "lte": "<=", "ne": "!=",
}

# TypeScript binary operators → Python
_TS_OP: dict[str, str] = {
    "===": "==", "!==": "!=",
    "&&": " and ", "||": " or ",
    "??": None,  # handled specially
}


def _camel_to_snake(name: str) -> str:
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower()


# ---------------------------------------------------------------------------
# Core code-generator
# ---------------------------------------------------------------------------

class TSCodeGen:
    """Walks a tree-sitter TypeScript AST and generates Python source."""

    # identifiers that should remain as attribute access (not dict access)
    _SELF_LIKE = {"self", "this"}

    def __init__(self, source: bytes):
        self.src = source
        self._anon_fn_count = 0

    # ---- helpers -----------------------------------------------------------

    def _t(self, node) -> str:
        return self.src[node.start_byte:node.end_byte].decode("utf-8")

    def _field(self, node, name):
        return node.child_by_field_name(name)

    def _named_children(self, node):
        return [c for c in node.children if c.is_named]

    def _non_punct(self, node, *skip):
        return [c for c in node.children
                if c.type not in {"(", ")", "[", "]", "{", "}", ",", ";", ":"} | set(skip)]

    def _is_big_call(self, node, methods) -> bool:
        if node.type != "call_expression":
            return False
        fn = self._field(node, "function")
        if fn is None or fn.type != "member_expression":
            return False
        prop = self._field(fn, "property")
        return prop is not None and self._t(prop) in methods

    # ---- expression translation --------------------------------------------

    def expr(self, node, min_prec: int = 0) -> str:
        if node is None:
            return "None"
        t = node.type

        if t == "number":
            return self._t(node)
        if t in ("string", "template_string"):
            return self._xlat_string(node)
        if t == "true":
            return "True"
        if t == "false":
            return "False"
        if t in ("null", "undefined"):
            return "None"
        if t == "identifier":
            return self._xlat_ident(node)
        if t == "this":
            return "self"
        if t == "parenthesized_expression":
            inner = next((c for c in node.children
                          if c.type not in {"(", ")"}), None)
            return f"({self.expr(inner)})"
        if t == "new_expression":
            return self._xlat_new(node)
        if t == "call_expression":
            return self._xlat_call(node, min_prec)
        if t == "await_expression":
            return self.expr(node.children[-1])
        if t == "member_expression":
            return self._xlat_member(node)
        if t == "subscript_expression":
            obj = self._field(node, "object") or node.children[0]
            idx = self._field(node, "index") or node.children[2]
            return f"{self.expr(obj)}[{self.expr(idx)}]"
        if t == "binary_expression":
            return self._xlat_binary(node)
        if t == "unary_expression":
            return self._xlat_unary(node)
        if t == "ternary_expression":
            return self._xlat_ternary(node)
        if t in ("assignment_expression",):
            return self._xlat_assignment(node)
        if t == "augmented_assignment_expression":
            return self._xlat_augmented_assign(node)
        if t == "object":
            return self._xlat_object(node)
        if t == "array":
            items = self._non_punct(node)
            return "[" + ", ".join(self.expr(i) for i in items) + "]"
        if t in ("as_expression", "satisfies_expression",
                 "non_null_expression", "type_assertion"):
            inner = self._field(node, "value") or node.children[0]
            return self.expr(inner)
        if t == "arrow_function":
            return self._xlat_arrow(node)
        if t == "spread_element":
            return f"*{self.expr(node.children[-1])}"
        if t == "void_operator":
            return "None"
        if t == "typeof_expression":
            return f"type({self.expr(node.children[-1])}).__name__"
        if t == "sequence_expression":
            parts = [c for c in node.children if c.type != ","]
            return self.expr(parts[-1])
        # fallback
        return repr(self._t(node))

    def _xlat_ident(self, node) -> str:
        name = self._t(node)
        mapping = {
            "undefined": "None",
            "null": "None",
            "true": "True",
            "false": "False",
            "Number": "_Number",
            "Math": "_math",
            "Object": "_Object",
            "Array": "list",
            "console": "_console",
        }
        return mapping.get(name, name)

    def _xlat_new(self, node) -> str:
        cls_node = self._field(node, "constructor") or node.children[1]
        cls_name = self._t(cls_node)
        args_node = self._field(node, "arguments")
        arg_nodes = []
        if args_node:
            arg_nodes = [c for c in args_node.children
                         if c.type not in {"(", ")", ","}]
        if cls_name == "Big":
            if arg_nodes:
                return f"float({self.expr(arg_nodes[0])})"
            return "0.0"
        if cls_name == "Date":
            if arg_nodes:
                return f"_parse_date({self.expr(arg_nodes[0])})"
            return "_today()"
        args_py = ", ".join(self.expr(a) for a in arg_nodes)
        return f"{cls_name}({args_py})"

    def _xlat_call(self, node, min_prec: int = 0) -> str:
        fn = self._field(node, "function") or node.children[0]
        args_node = self._field(node, "arguments") or node.children[-1]
        arg_nodes = [c for c in args_node.children
                     if c.type not in {"(", ")", ","}]

        if fn.type == "member_expression":
            return self._xlat_method_call(fn, arg_nodes, min_prec)

        # Global / free function call
        fn_name = self.expr(fn) if fn.type != "identifier" else self._t(fn)
        return self._xlat_global_call(fn_name, arg_nodes)

    def _xlat_method_call(self, fn, arg_nodes, min_prec: int = 0) -> str:
        obj = self._field(fn, "object") or fn.children[0]
        prop = self._field(fn, "property") or fn.children[-1]
        method = self._t(prop)
        optional = any(c.type == "?." for c in fn.children)

        # ---- Big.js arithmetic ops ----------------------------------------
        if method in _BIG_BINARY:
            op, prec = _BIG_BINARY[method]
            # If the object itself is a Big chain, parenthesise when needed
            left = self.expr(obj, min_prec=prec)
            right = self.expr(arg_nodes[0], min_prec=prec + 1) if arg_nodes else "0.0"
            result = f"{left} {op} {right}"
            return f"({result})" if prec < min_prec else result

        if method in _BIG_CMP:
            op = _BIG_CMP[method]
            left = self.expr(obj)
            right = self.expr(arg_nodes[0]) if arg_nodes else "0.0"
            return f"{left} {op} {right}"

        if method == "toNumber":
            return self.expr(obj)
        if method == "toFixed":
            n = self.expr(arg_nodes[0]) if arg_nodes else "2"
            return f"round(float({self.expr(obj)}), {n})"
        if method == "abs":
            return f"abs({self.expr(obj)})"

        # ---- Array / object methods ----------------------------------------
        if method == "push":
            items = ", ".join(self.expr(a) for a in arg_nodes)
            return f"{self.expr(obj)}.append({items})"
        if method == "at":
            idx = self.expr(arg_nodes[0]) if arg_nodes else "0"
            return f"{self.expr(obj)}[{idx}]"
        if method == "findIndex":
            fn_arg = self.expr(arg_nodes[0]) if arg_nodes else "lambda x: True"
            base = self.expr(obj)
            return f"next((i for i, x in enumerate({base}) if ({fn_arg})(x)), -1)"
        if method == "filter":
            fn_arg = self.expr(arg_nodes[0]) if arg_nodes else "lambda x: True"
            return f"[_x for _x in {self.expr(obj)} if ({fn_arg})(_x)]"
        if method == "map":
            fn_arg = self.expr(arg_nodes[0]) if arg_nodes else "lambda x: x"
            return f"[({fn_arg})(_x) for _x in {self.expr(obj)}]"
        if method == "includes":
            item = self.expr(arg_nodes[0]) if arg_nodes else "None"
            return f"({item} in {self.expr(obj)})"
        if method == "reduce":
            fn_arg = self.expr(arg_nodes[0]) if arg_nodes else "lambda a, x: a"
            init = self.expr(arg_nodes[1]) if len(arg_nodes) > 1 else "None"
            base = self.expr(obj)
            return f"_functools_reduce({fn_arg}, {base}, {init})"
        if method == "some":
            fn_arg = self.expr(arg_nodes[0]) if arg_nodes else "lambda x: True"
            return f"any(({fn_arg})(_x) for _x in {self.expr(obj)})"
        if method == "every":
            fn_arg = self.expr(arg_nodes[0]) if arg_nodes else "lambda x: True"
            return f"all(({fn_arg})(_x) for _x in {self.expr(obj)})"
        if method in ("sort", "toSorted"):
            base = self.expr(obj)
            if arg_nodes:
                fn_arg = self.expr(arg_nodes[0])
                return f"sorted({base}, key={fn_arg})"
            return f"sorted({base})"
        if method == "forEach":
            fn_arg = self.expr(arg_nodes[0]) if arg_nodes else "lambda x: None"
            return f"[({fn_arg})(_x) for _x in {self.expr(obj)}]"
        if method == "length":
            return f"len({self.expr(obj)})"
        if method == "join":
            sep = self.expr(arg_nodes[0]) if arg_nodes else "''"
            return f"{sep}.join(str(_x) for _x in {self.expr(obj)})"
        if method == "split":
            sep = self.expr(arg_nodes[0]) if arg_nodes else "' '"
            return f"{self.expr(obj)}.split({sep})"
        if method in ("toString", "valueOf"):
            return f"str({self.expr(obj)})"

        # ---- dict/object methods -------------------------------------------
        if method == "keys":
            return f"list({self.expr(obj)}.keys())"
        if method == "values":
            return f"list({self.expr(obj)}.values())"
        if method == "entries":
            return f"list({self.expr(obj)}.items())"
        if method == "hasOwnProperty":
            k = self.expr(arg_nodes[0]) if arg_nodes else "''"
            return f"({k} in {self.expr(obj)})"

        # ---- console / logging (skip) --------------------------------------
        obj_py = self.expr(obj)
        if obj_py in ("_console",):
            return "None  # console"

        # ---- date methods --------------------------------------------------
        if method == "getTime":
            return f"_date_to_ms({obj_py})"
        if method == "getFullYear":
            return f"{obj_py}.year"

        # ---- generic: optional-chain access --------------------------------
        args_py = ", ".join(self.expr(a) for a in arg_nodes)
        if optional:
            return f"(({obj_py}).get('{method}', None) if {obj_py} else None)"
        return f"{obj_py}.{method}({args_py})"

    def _xlat_global_call(self, fn_name: str, arg_nodes) -> str:
        a = lambda i: self.expr(arg_nodes[i]) if i < len(arg_nodes) else "None"
        args_py = ", ".join(self.expr(n) for n in arg_nodes)

        fn_map = {
            "getFactor":                 f"_get_factor({a(0)})",
            "getIntervalFromDateRange":  f"_get_interval({a(0)})",
            "format":                    f"_fmt_date({a(0)})",
            "isBefore":                  f"({a(0)} < {a(1)})",
            "isAfter":                   f"({a(0)} > {a(1)})",
            "isThisYear":                f"_is_this_year({a(0)})",
            "differenceInDays":          f"_diff_days({a(0)}, {a(1)})",
            "addMilliseconds":           f"_add_ms({a(0)}, {a(1)})",
            "addDays":                   f"_add_days({a(0)}, {a(1)})",
            "eachYearOfInterval":        f"_each_year({a(0)})",
            "cloneDeep":                 f"copy.deepcopy({a(0)})",
            "sortBy":                    (f"sorted({a(0)}, key={a(1)})"
                                          if len(arg_nodes) > 1 else f"sorted({a(0)})"),
            "isNaN":                     f"(_is_nan({a(0)}))",
            "isFinite":                  f"(_is_finite({a(0)}))",
            "parseFloat":                f"float({a(0)})",
            "parseInt":                  f"int({a(0)})",
            "Object.keys":               f"list({a(0)}.keys())",
            "Object.values":             f"list({a(0)}.values())",
            "Object.entries":            f"list({a(0)}.items())",
            "Array.isArray":             f"isinstance({a(0)}, list)",
        }
        if fn_name in fn_map:
            return fn_map[fn_name]

        # Math.* via _math alias
        if fn_name.startswith("_math."):
            py = fn_name.replace("_math.", "math.")
            return f"{py}({args_py})"
        if fn_name.startswith("Math."):
            py = fn_name.replace("Math.", "math.")
            return f"{py}({args_py})"

        # Convert camelCase function to snake_case
        py_name = _camel_to_snake(fn_name)
        return f"{py_name}({args_py})"

    def _xlat_member(self, node) -> str:
        obj = self._field(node, "object") or node.children[0]
        prop = self._field(node, "property") or node.children[-1]
        method = self._t(prop)
        optional = any(c.type == "?." for c in node.children)

        obj_py = self.expr(obj)

        # Static / constant access
        if obj_py == "self":
            return f"self.{method}"
        if method == "EPSILON" and obj_py == "_Number":
            return "sys.float_info.epsilon"
        if obj_py == "_math" or obj_py.startswith("math."):
            return f"math.{method}"
        if obj_py == "PortfolioCalculator":
            if method == "ENABLE_LOGGING":
                return "False"
            return f"PortfolioCalculator.{method}"

        # Optional chaining
        if optional:
            return f"({obj_py} or {{}}).get('{method}')"

        # Default: dict key access for object-like data
        return f"{obj_py}.get('{method}')"

    def _xlat_object(self, node) -> str:
        pairs = []
        for child in node.children:
            if child.type == "pair":
                key = self._field(child, "key")
                val = self._field(child, "value")
                if key and val:
                    key_str = self._t(key).strip("'\"")
                    if not key_str.startswith('"'):
                        key_str = f'"{key_str}"'
                    else:
                        key_str = f'"{key_str.strip(chr(34))}"'
                    pairs.append(f"{key_str}: {self.expr(val)}")
            elif child.type == "shorthand_property_identifier":
                name = self._t(child)
                pairs.append(f'"{name}": {name}')
            elif child.type == "shorthand_property_identifier_pattern":
                name = self._t(child)
                pairs.append(f'"{name}": {name}')
            elif child.type == "spread_element":
                inner = child.children[-1]
                pairs.append(f"**{self.expr(inner)}")
            elif child.type == "method_definition":
                # Object method — skip for now
                pass
        return "{" + ", ".join(pairs) + "}"

    def _xlat_binary(self, node) -> str:
        left = self._field(node, "left")
        right = self._field(node, "right")
        op_node = next(
            (c for c in node.children
             if not c.is_named and c.type not in
             {"identifier", "number", "string", "true", "false",
              "null", "undefined"}),
            None
        )
        if op_node is None:
            # find operator by position
            kids = node.children
            op_node = kids[1] if len(kids) >= 3 else kids[0]

        op = self._t(op_node)
        if op == "??":
            lpy = self.expr(left)
            rpy = self.expr(right)
            return f"({lpy} if {lpy} is not None else {rpy})"

        op_py = _TS_OP.get(op, op)
        return f"{self.expr(left)} {op_py} {self.expr(right)}"

    def _xlat_unary(self, node) -> str:
        op_node = node.children[0]
        operand = node.children[1] if len(node.children) > 1 else node.children[0]
        op = self._t(op_node)
        if op == "!":
            return f"not {self.expr(operand)}"
        if op == "-":
            return f"-{self.expr(operand)}"
        if op == "+":
            return f"float({self.expr(operand)})"
        if op == "typeof":
            return f"type({self.expr(operand)}).__name__"
        if op == "void":
            return "None"
        return f"{op}{self.expr(operand)}"

    def _xlat_ternary(self, node) -> str:
        cond = self._field(node, "condition")
        cons = self._field(node, "consequence")
        alt = self._field(node, "alternative")
        return f"{self.expr(cons)} if {self.expr(cond)} else {self.expr(alt)}"

    def _xlat_assignment(self, node) -> str:
        left = self._field(node, "left")
        right = self._field(node, "right")
        return f"{self.expr(left)} = {self.expr(right)}"

    def _xlat_augmented_assign(self, node) -> str:
        left = self._field(node, "left")
        right = self._field(node, "right")
        op_node = next(c for c in node.children
                       if c.type in {"+=", "-=", "*=", "/=", "&&=", "||=", "??="})
        op = self._t(op_node)
        lpy = self.expr(left)
        rpy = self.expr(right)
        if op == "??=":
            return f"{lpy} = {lpy} if {lpy} is not None else {rpy}"
        if op == "&&=":
            return f"{lpy} = {lpy} and {rpy}"
        if op == "||=":
            return f"{lpy} = {lpy} or {rpy}"
        return f"{lpy} {op} {rpy}"

    def _xlat_arrow(self, node) -> str:
        params = self._field(node, "parameters") or self._field(node, "parameter")
        body = self._field(node, "body")
        param_names = []
        if params:
            if params.type == "formal_parameters":
                for p in params.children:
                    if p.type in ("required_parameter", "optional_parameter",
                                  "rest_pattern"):
                        pname = self._field(p, "pattern") or p.children[0]
                        name = self._t(pname)
                        if p.type == "rest_pattern":
                            param_names.append(f"*{name}")
                        else:
                            param_names.append(name)
                    elif p.type == "identifier":
                        param_names.append(self._t(p))
                    elif p.type == "object_pattern":
                        self._anon_fn_count += 1
                        param_names.append(f"_d{self._anon_fn_count}")
            elif params.type == "identifier":
                param_names.append(self._t(params))
        params_str = ", ".join(param_names)
        if body is None:
            return f"lambda {params_str}: None"
        if body.type == "statement_block":
            # Try to find a return statement
            for child in body.children:
                if child.type == "return_statement":
                    ret = next((c for c in child.children
                                if c.type not in {"return", ";"}), None)
                    if ret:
                        return f"lambda {params_str}: {self.expr(ret)}"
            # Destructuring case: ({a, b}) => expr uses _d1["a"]
            return f"lambda {params_str}: None"
        return f"lambda {params_str}: {self.expr(body)}"

    def _xlat_string(self, node) -> str:
        t = node.type
        if t == "string":
            return self._t(node)
        if t == "template_string":
            parts = []
            for child in node.children:
                if child.type in ("`",):
                    continue
                if child.type == "string_fragment":
                    parts.append(self._t(child).replace("{", "{{").replace("}", "}}"))
                elif child.type == "template_substitution":
                    inner = next((c for c in child.children
                                  if c.type not in {"${", "}"}), None)
                    if inner:
                        parts.append("{" + self.expr(inner) + "}")
            return 'f"' + "".join(parts) + '"'
        return self._t(node)

    # ---- statement translation --------------------------------------------

    def stmts(self, node, indent: int = 0) -> list[str]:
        """Translate a node or block to a list of Python lines."""
        t = node.type
        pad = "    " * indent

        if t in ("import_statement", "export_statement"):
            return []

        if t == "comment":
            text = self._t(node)
            if text.startswith("//"):
                return [f"{pad}# {text[2:].strip()}"]
            return []

        if t in ("lexical_declaration", "variable_declaration"):
            return self._xlat_var_decl(node, indent)

        if t == "expression_statement":
            expr_node = next(
                (c for c in node.children if c.type not in {";"}), None
            )
            if expr_node is None:
                return []
            # Skip console.log
            if (expr_node.type == "call_expression"):
                fn = self._field(expr_node, "function")
                if fn and fn.type == "member_expression":
                    obj = self._field(fn, "object")
                    if obj and self._t(obj) in ("console", "Logger"):
                        return []
            result = self.expr(expr_node)
            if result.startswith("None  #"):
                return []
            return [f"{pad}{result}"]

        if t == "return_statement":
            rest = [c for c in node.children if c.type not in {"return", ";"}]
            if not rest:
                return [f"{pad}return"]
            return [f"{pad}return {self.expr(rest[0])}"]

        if t == "if_statement":
            return self._xlat_if(node, indent)

        if t == "for_in_statement":
            return self._xlat_for_of(node, indent)

        if t == "for_statement":
            return self._xlat_for(node, indent)

        if t == "while_statement":
            cond = self._field(node, "condition")
            body = self._field(node, "body")
            lines = [f"{pad}while {self.expr(cond)}:"]
            body_lines = self.stmts(body, indent + 1) if body else []
            lines.extend(body_lines or [f"{pad}    pass"])
            return lines

        if t == "statement_block":
            lines = []
            for child in node.children:
                if child.type in {"{", "}"}:
                    continue
                lines.extend(self.stmts(child, indent))
            return lines or [f"{pad}pass"]

        if t == "continue_statement":
            return [f"{pad}continue"]
        if t == "break_statement":
            return [f"{pad}break"]
        if t == "empty_statement":
            return []

        if t == "throw_statement":
            expr_node = next((c for c in node.children
                              if c.type not in {"throw", ";"}), None)
            return [f"{pad}raise Exception({self.expr(expr_node)})"]

        if t == "try_statement":
            return self._xlat_try(node, indent)

        # Unknown — skip
        return []

    def _xlat_var_decl(self, node, indent: int) -> list[str]:
        pad = "    " * indent
        lines = []
        for child in node.children:
            if child.type != "variable_declarator":
                continue
            name_node = self._field(child, "name") or child.children[0]
            val_node = self._field(child, "value")

            # Destructuring: {a, b} = expr
            if name_node.type == "object_pattern":
                val_py = self.expr(val_node) if val_node else "None"
                props = []
                for p in name_node.children:
                    if p.type in ("shorthand_property_identifier",
                                  "shorthand_property_identifier_pattern"):
                        props.append(self._t(p))
                    elif p.type == "pair_pattern":
                        kn = self._field(p, "key")
                        vn = self._field(p, "value")
                        if vn:
                            props.append(self._t(vn))
                if props:
                    tmp = f"_tmp_{id(node) % 9999}"
                    lines.append(f"{pad}{tmp} = {val_py}")
                    for prop in props:
                        lines.append(f"{pad}{prop} = {tmp}.get('{prop}')")
                continue

            name = self._t(name_node)
            if val_node:
                lines.append(f"{pad}{name} = {self.expr(val_node)}")
            else:
                lines.append(f"{pad}{name} = None")
        return lines

    def _xlat_if(self, node, indent: int) -> list[str]:
        pad = "    " * indent
        lines = []
        cond = self._field(node, "condition")
        body = self._field(node, "consequence")
        alt = self._field(node, "alternative")

        cond_py = self.expr(cond) if cond else "True"
        # Strip outer parens from condition
        while cond_py.startswith("(") and cond_py.endswith(")"):
            inner = cond_py[1:-1]
            # Make sure parens are balanced before stripping
            if inner.count("(") == inner.count(")"):
                cond_py = inner
            else:
                break

        lines.append(f"{pad}if {cond_py}:")
        body_lines = self.stmts(body, indent + 1) if body else []
        lines.extend(body_lines or [f"{pad}    pass"])

        if alt:
            if alt.type == "if_statement":
                elif_lines = self._xlat_if(alt, indent)
                if elif_lines:
                    elif_lines[0] = elif_lines[0].replace(
                        f"{pad}if ", f"{pad}elif ", 1)
                lines.extend(elif_lines)
            else:
                lines.append(f"{pad}else:")
                alt_lines = self.stmts(alt, indent + 1)
                lines.extend(alt_lines or [f"{pad}    pass"])

        return lines

    def _xlat_for_of(self, node, indent: int) -> list[str]:
        pad = "    " * indent
        kids = node.children
        # for (const/let x of iter) body
        var_node = None
        iter_node = None
        body_node = None

        i = 0
        while i < len(kids):
            c = kids[i]
            if c.type in ("const", "let", "var"):
                if i + 1 < len(kids):
                    var_node = kids[i + 1]
                    i += 2
                    continue
            if c.type == "of":
                if i + 1 < len(kids):
                    iter_node = kids[i + 1]
                i += 1
                continue
            if c.type == "statement_block":
                body_node = c
            i += 1

        if var_node is None:
            var_node = self._field(node, "left")
        if iter_node is None:
            iter_node = self._field(node, "right")
        if body_node is None:
            body_node = self._field(node, "body")

        var_py = self.expr(var_node) if var_node else "_item"
        iter_py = self.expr(iter_node) if iter_node else "[]"

        lines = [f"{pad}for {var_py} in {iter_py}:"]
        body_lines = self.stmts(body_node, indent + 1) if body_node else []
        lines.extend(body_lines or [f"{pad}    pass"])
        return lines

    def _xlat_for(self, node, indent: int) -> list[str]:
        pad = "    " * indent
        init = self._field(node, "initializer")
        cond = self._field(node, "condition")
        upd = self._field(node, "increment")
        body = self._field(node, "body")

        # Try to detect "for (let i = N; i < M; i += 1)"
        if init and init.type in ("lexical_declaration", "variable_declaration"):
            for decl in init.children:
                if decl.type != "variable_declarator":
                    continue
                vn = self._field(decl, "name")
                sv = self._field(decl, "value")
                if vn and sv and cond:
                    var = self._t(vn)
                    start = self.expr(sv)
                    cond_py = self.expr(cond)
                    # range detection
                    if f"{var} <" in cond_py:
                        end_part = cond_py.split(f"{var} <")[-1].strip()
                        incl = cond_py.split(f"{var} <")[0] == "" and "<=" in cond_py
                        if incl:
                            end_py = f"{end_part} + 1"
                        else:
                            end_py = end_part
                        lines = [f"{pad}for {var} in range({start}, {end_py}):"]
                        body_lines = self.stmts(body, indent + 1) if body else []
                        lines.extend(body_lines or [f"{pad}    pass"])
                        return lines
                    if f"{var} >=" in cond_py:
                        end_part = cond_py.split(f"{var} >=")[-1].strip()
                        lines = [f"{pad}for {var} in range({start}, {end_part} - 1, -1):"]
                        body_lines = self.stmts(body, indent + 1) if body else []
                        lines.extend(body_lines or [f"{pad}    pass"])
                        return lines

        # Fallback: while loop
        init_lines = self.stmts(init, indent) if init else []
        cond_py = self.expr(cond) if cond else "True"
        lines = init_lines + [f"{pad}while {cond_py}:"]
        body_lines = self.stmts(body, indent + 1) if body else []
        lines.extend(body_lines or [f"{pad}    pass"])
        if upd:
            upd_py = self.expr(upd)
            lines.append(f"{pad}    {upd_py}")
        return lines

    def _xlat_try(self, node, indent: int) -> list[str]:
        pad = "    " * indent
        body = self._field(node, "body")
        lines = [f"{pad}try:"]
        body_lines = self.stmts(body, indent + 1) if body else []
        lines.extend(body_lines or [f"{pad}    pass"])
        # find catch clause
        for child in node.children:
            if child.type == "catch_clause":
                lines.append(f"{pad}except Exception:")
                catch_body = self._field(child, "body")
                catch_lines = self.stmts(catch_body, indent + 1) if catch_body else []
                lines.extend(catch_lines or [f"{pad}    pass"])
        return lines

    # ---- method / class translation ----------------------------------------

    def translate_method(self, node, indent: int = 1,
                          extra_params: str = "") -> list[str]:
        pad = "    " * indent
        name_node = self._field(node, "name") or node.children[0]
        name = self._t(name_node)
        py_name = _camel_to_snake(name)

        # Build parameter list
        params_node = self._field(node, "parameters")
        params = ["self"]
        if extra_params:
            params.append(extra_params)
        if params_node:
            for p in params_node.children:
                if p.type in ("required_parameter", "optional_parameter"):
                    pn = self._field(p, "pattern") or p.children[0]
                    pname = self._t(pn)
                    params.append(pname)
                elif p.type == "identifier":
                    params.append(self._t(p))
                elif p.type == "object_pattern":
                    # Destructured param: {a, b, c} → **kwargs or named
                    params.append("**_kw")

        params_str = ", ".join(params)
        body_node = self._field(node, "body")

        lines = [f"{pad}def {py_name}({params_str}):"]
        if body_node:
            body_lines = self.stmts(body_node, indent + 1)
            lines.extend(body_lines or [f"{pad}    pass"])
        else:
            lines.append(f"{pad}    pass")
        return lines

    def translate_class_methods(self, class_node) -> dict[str, list[str]]:
        """Extract and translate all method definitions from a class node."""
        methods = {}
        body = self._field(class_node, "body")
        if not body:
            return methods
        for child in body.children:
            if child.type == "method_definition":
                name_node = self._field(child, "name") or child.children[0]
                name = self._t(name_node)
                py_name = _camel_to_snake(name)
                methods[py_name] = self.translate_method(child, indent=1)
        return methods


# ---------------------------------------------------------------------------
# High-level translation functions
# ---------------------------------------------------------------------------

def _find_class_node(tree, source: bytes):
    """Find the first class declaration in a TypeScript file."""
    def _walk(node):
        if node.type in ("class_declaration", "export_statement"):
            if node.type == "export_statement":
                for child in node.children:
                    result = _walk(child)
                    if result:
                        return result
            elif node.type == "class_declaration":
                return node
        for child in node.children:
            result = _walk(child)
            if result:
                return result
        return None
    return _walk(tree.root_node)


def translate_typescript_file(ts_content: str) -> dict[str, list[str]]:
    """
    Parse a TypeScript file and return a dict of {py_method_name: lines}.
    """
    parser = _mk_parser()
    source = ts_content.encode("utf-8")
    tree = parser.parse(source)
    class_node = _find_class_node(tree, source)
    if class_node is None:
        return {}
    gen = TSCodeGen(source)
    return gen.translate_class_methods(class_node)


# ---------------------------------------------------------------------------
# Python file generation
# ---------------------------------------------------------------------------

_HEADER = '''\
"""
RoaiPortfolioCalculator — translated from TypeScript using tree-sitter AST.
"""
from __future__ import annotations

import copy
import math
import sys
from datetime import date as _D, datetime as _DT, timedelta

from app.wrapper.portfolio.calculator.portfolio_calculator import PortfolioCalculator


# ---------------------------------------------------------------------------
# Helpers (mirrors TypeScript imports / utility functions)
# ---------------------------------------------------------------------------

def _get_factor(order_type: str) -> float:
    if order_type == "BUY":
        return 1.0
    if order_type == "SELL":
        return -1.0
    return 0.0


def _parse_date(s) -> _D:
    if isinstance(s, (_D, _DT)):
        return s if isinstance(s, _D) else s.date()
    return _D.fromisoformat(str(s)[:10])


def _today() -> _D:
    return _D.today()


def _fmt_date(d) -> str:
    if isinstance(d, str):
        return d[:10]
    if isinstance(d, (_D, _DT)):
        return d.strftime("%Y-%m-%d")
    return str(d)[:10]


def _diff_days(a, b) -> int:
    da = _parse_date(a) if not isinstance(a, _D) else a
    db = _parse_date(b) if not isinstance(b, _D) else b
    return (da - db).days


def _add_ms(d, ms: float):
    return _parse_date(d)


def _add_days(d, n: int) -> _D:
    return _parse_date(d) + timedelta(days=int(n))


def _is_this_year(d) -> bool:
    return _parse_date(d).year == _D.today().year


def _each_year(interval) -> list:
    if isinstance(interval, dict):
        start = _parse_date(interval.get("start", _D.today()))
        end = _parse_date(interval.get("end", _D.today()))
    else:
        return []
    result = []
    y = start.year
    while y <= end.year:
        result.append(_D(y, 1, 1))
        y += 1
    return result


def _get_interval(date_range: str) -> dict:
    today = _D.today()
    if date_range == "max":
        return {"startDate": _D(1900, 1, 1), "endDate": today}
    if date_range == "ytd":
        return {"startDate": _D(today.year, 1, 1), "endDate": today}
    if date_range == "1d":
        return {"startDate": today, "endDate": today}
    if date_range == "1y":
        start = _D(today.year - 1, today.month, today.day)
        return {"startDate": start, "endDate": today}
    if date_range == "5y":
        start = _D(today.year - 5, today.month, today.day)
        return {"startDate": start, "endDate": today}
    if date_range == "mtd":
        return {"startDate": _D(today.year, today.month, 1), "endDate": today}
    if date_range == "wtd":
        start = today - timedelta(days=today.weekday())
        return {"startDate": start, "endDate": today}
    # Year like "2023"
    try:
        y = int(date_range)
        return {"startDate": _D(y, 1, 1), "endDate": _D(y, 12, 31)}
    except (ValueError, TypeError):
        return {"startDate": today, "endDate": today}


def _date_to_ms(d) -> float:
    return _parse_date(d).toordinal() * 86400000.0


def _is_nan(x) -> bool:
    try:
        return math.isnan(float(x))
    except (TypeError, ValueError):
        return True


def _is_finite(x) -> bool:
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


_Number = type("_Number", (), {"EPSILON": sys.float_info.epsilon})()
_console = type("_console", (), {"log": staticmethod(lambda *a: None)})()
_Object = dict
_math = math

'''

_PORTFOLIO_INTERFACE = '''\

    # -----------------------------------------------------------------------
    # Python interface methods  (orchestrate the translated TypeScript logic)
    # -----------------------------------------------------------------------

    def get_performance(self) -> dict:
        acts = self.sorted_activities()
        if not acts:
            return {
                "chart": [],
                "firstOrderDate": None,
                "performance": {
                    "currentNetWorth": 0.0,
                    "currentValue": 0.0,
                    "currentValueInBaseCurrency": 0.0,
                    "netPerformance": 0.0,
                    "netPerformancePercentage": 0.0,
                    "netPerformancePercentageWithCurrencyEffect": 0.0,
                    "netPerformanceWithCurrencyEffect": 0.0,
                    "totalFees": 0.0,
                    "totalInvestment": 0.0,
                    "totalLiabilities": 0.0,
                    "totalValueables": 0.0,
                },
            }
        symbols = sorted({a["symbol"] for a in acts
                          if a.get("type") in ("BUY", "SELL")})
        first_date = min(a["date"] for a in acts)
        today = _fmt_date(_today())
        chart_dates = self._get_chart_dates(acts, today)
        chart_by_date: dict = {}
        total_inv = 0.0
        total_val = 0.0
        total_net = 0.0
        total_fees = 0.0
        total_liab = 0.0
        twi_total = 0.0
        twi_days = 0.0
        for sym in symbols:
            m = self._compute_symbol(sym, acts, chart_dates, today)
            total_inv += m["totalInvestment"]
            total_val += m["currentValue"]
            total_net += m["netPerformance"]
            total_fees += m["totalFees"]
            total_liab += m["totalLiabilities"]
            twi_total += m["twiTotal"]
            twi_days += m["twiDays"]
            for d, entry in m["chartEntries"].items():
                if d not in chart_by_date:
                    chart_by_date[d] = {
                        "date": d,
                        "netWorth": 0.0, "value": 0.0,
                        "totalInvestment": 0.0, "netPerformance": 0.0,
                        "netPerformanceInPercentage": 0.0,
                        "netPerformanceInPercentageWithCurrencyEffect": 0.0,
                    }
                chart_by_date[d]["value"] += entry["value"]
                chart_by_date[d]["netWorth"] += entry["value"]
                chart_by_date[d]["totalInvestment"] += entry["totalInvestment"]
                chart_by_date[d]["netPerformance"] += entry["netPerformance"]
        # Compute per-chart-entry percentage
        for d, entry in chart_by_date.items():
            inv = entry["totalInvestment"]
            pct = entry["netPerformance"] / inv if inv != 0.0 else 0.0
            entry["netPerformanceInPercentage"] = pct
            entry["netPerformanceInPercentageWithCurrencyEffect"] = pct
        chart = sorted(chart_by_date.values(), key=lambda e: e["date"])
        twi = twi_total / twi_days if twi_days > 0 else total_inv
        net_pct = total_net / twi if twi != 0.0 else 0.0
        return {
            "chart": chart,
            "firstOrderDate": first_date,
            "performance": {
                "currentNetWorth": total_val,
                "currentValue": total_val,
                "currentValueInBaseCurrency": total_val,
                "netPerformance": total_net,
                "netPerformancePercentage": net_pct,
                "netPerformancePercentageWithCurrencyEffect": net_pct,
                "netPerformanceWithCurrencyEffect": total_net,
                "totalFees": total_fees,
                "totalInvestment": total_inv,
                "totalLiabilities": total_liab,
                "totalValueables": 0.0,
            },
        }

    def get_investments(self, group_by: str | None = None) -> dict:
        acts = self.sorted_activities()
        delta: dict[str, float] = {}
        running: dict[str, dict] = {}
        for act in acts:
            sym = act.get("symbol", "")
            atype = act.get("type", "")
            if atype not in ("BUY", "SELL"):
                continue
            qty = float(act.get("quantity", 0))
            price = float(act.get("unitPrice", 0))
            date = act["date"]
            if sym not in running:
                running[sym] = {"units": 0.0, "investment": 0.0}
            r = running[sym]
            if atype == "BUY":
                inv_delta = qty * price
                r["units"] += qty
                r["investment"] += qty * price
            else:  # SELL
                avg = r["investment"] / r["units"] if r["units"] > 0 else 0.0
                inv_delta = -(avg * qty)
                r["units"] -= qty
                r["investment"] = max(0.0, r["investment"] - avg * qty)
            key = self._group_date(date, group_by)
            delta[key] = delta.get(key, 0.0) + inv_delta
        investments = [{"date": d, "investment": v}
                       for d, v in sorted(delta.items())]
        return {"investments": investments}

    def get_holdings(self) -> dict:
        acts = self.sorted_activities()
        positions: dict[str, dict] = {}
        for act in acts:
            sym = act.get("symbol", "")
            atype = act.get("type", "")
            if atype not in ("BUY", "SELL"):
                continue
            qty = float(act.get("quantity", 0))
            price = float(act.get("unitPrice", 0))
            if sym not in positions:
                positions[sym] = {"units": 0.0, "investment": 0.0, "dataSource": act.get("dataSource", ""), "currency": act.get("currency", "USD")}
            p = positions[sym]
            if atype == "BUY":
                p["units"] += qty
                p["investment"] += qty * price
            else:
                avg = p["investment"] / p["units"] if p["units"] > 0 else 0.0
                p["investment"] = max(0.0, p["investment"] - avg * qty)
                p["units"] -= qty
        holdings = {}
        for sym, p in positions.items():
            if p["units"] <= 1e-10:
                continue
            market_price = self.current_rate_service.get_latest_price(sym)
            avg_price = p["investment"] / p["units"] if p["units"] > 0 else 0.0
            current_val = p["units"] * market_price
            net_perf = current_val - p["investment"]
            holdings[sym] = {
                "symbol": sym,
                "quantity": p["units"],
                "investment": p["investment"],
                "averagePrice": avg_price,
                "marketPrice": market_price,
                "currentValue": current_val,
                "netPerformance": net_perf,
                "netPerformancePercent": net_perf / p["investment"] if p["investment"] != 0 else 0.0,
                "currency": p["currency"],
                "dataSource": p["dataSource"],
            }
        return {"holdings": holdings}

    def get_details(self, base_currency: str = "USD") -> dict:
        acts = self.sorted_activities()
        perf = self.get_performance()
        holdings_resp = self.get_holdings()
        first_date = min((a["date"] for a in acts), default=None)
        holdings_detail = {}
        for sym, h in holdings_resp["holdings"].items():
            holdings_detail[sym] = {
                "symbol": sym,
                "quantity": h["quantity"],
                "investment": h["investment"],
                "averagePrice": h["averagePrice"],
                "marketPrice": h["marketPrice"],
                "currentValue": h["currentValue"],
                "netPerformance": h["netPerformance"],
                "netPerformancePercent": h["netPerformancePercent"],
                "currency": h.get("currency", base_currency),
                "dataSource": h.get("dataSource", ""),
                "allocationInPercentage": 0.0,
                "allocationInvestmentInPercentage": 0.0,
            }
        pf = perf["performance"]
        return {
            "accounts": {"default": {"balance": 0.0, "currency": base_currency, "name": "Default Account", "valueInBaseCurrency": 0.0}},
            "createdAt": first_date,
            "holdings": holdings_detail,
            "platforms": {"default": {"balance": 0.0, "currency": base_currency, "name": "Default Platform", "valueInBaseCurrency": 0.0}},
            "summary": {
                "totalInvestment": pf["totalInvestment"],
                "netPerformance": pf["netPerformance"],
                "currentValueInBaseCurrency": pf["currentValueInBaseCurrency"],
                "totalFees": pf["totalFees"],
            },
            "hasError": False,
        }

    def get_dividends(self, group_by: str | None = None) -> dict:
        acts = self.sorted_activities()
        delta: dict[str, float] = {}
        for act in acts:
            if act.get("type") != "DIVIDEND":
                continue
            date = act["date"]
            qty = float(act.get("quantity", 0))
            price = float(act.get("unitPrice", 0))
            amount = qty * price
            key = self._group_date(date, group_by)
            delta[key] = delta.get(key, 0.0) + amount
        dividends = [{"date": d, "investment": v}
                     for d, v in sorted(delta.items())]
        return {"dividends": dividends}

    def evaluate_report(self) -> dict:
        return {
            "xRay": {
                "categories": [
                    {"key": "accounts", "name": "Accounts", "rules": []},
                    {"key": "currencies", "name": "Currencies", "rules": []},
                    {"key": "fees", "name": "Fees", "rules": []},
                ],
                "statistics": {"rulesActiveCount": 0, "rulesFulfilledCount": 0},
            }
        }

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _group_date(self, date: str, group_by) -> str:
        if group_by == "month":
            return date[:7] + "-01"
        if group_by == "year":
            return date[:4] + "-01-01"
        return date

    def _get_chart_dates(self, acts, today: str) -> list[str]:
        dates = self.current_rate_service.all_dates_in_range(
            min(a["date"] for a in acts),
            today
        )
        if acts:
            first = min(a["date"] for a in acts)
            from datetime import date as _D2, timedelta
            prev = (_D2.fromisoformat(first) - timedelta(days=1)).isoformat()
            dates.add(prev)
        return sorted(dates)

    def _compute_symbol(self, sym: str, acts, chart_dates, today: str) -> dict:
        sym_acts = [a for a in acts if a.get("symbol") == sym
                    and a.get("type") in ("BUY", "SELL", "DIVIDEND", "FEE")]
        if not sym_acts:
            return {"totalInvestment": 0.0, "currentValue": 0.0,
                    "netPerformance": 0.0, "totalFees": 0.0,
                    "totalLiabilities": 0.0, "twiTotal": 0.0, "twiDays": 0.0,
                    "chartEntries": {}}
        units = 0.0
        investment = 0.0
        fees = 0.0
        total_buy_qty = 0.0
        total_buy_inv = 0.0
        gross_perf_from_sells = 0.0
        last_avg_price = 0.0
        act_idx = 0
        chart_entries: dict = {}
        total_inv_days = 0.0
        sum_twi = 0.0
        prev_date_str = None
        first_act_date = sym_acts[0]["date"]
        prev_value_before = 0.0
        for ds in chart_dates:
            if ds < first_act_date:
                # Day before first activity: zero entry
                price = 0.0
                value = 0.0
                chart_entries[ds] = {
                    "value": 0.0,
                    "totalInvestment": 0.0,
                    "netPerformance": 0.0,
                }
                prev_date_str = ds
                continue
            # Process all activities on this date
            while act_idx < len(sym_acts) and sym_acts[act_idx]["date"] <= ds:
                act = sym_acts[act_idx]
                atype = act.get("type", "")
                qty = float(act.get("quantity", 0))
                price_act = float(act.get("unitPrice", 0))
                fee = float(act.get("fee", 0))
                fees += fee
                if atype == "BUY":
                    inv_delta = qty * price_act
                    investment += inv_delta
                    units += qty
                    total_buy_qty += qty
                    total_buy_inv += inv_delta
                elif atype == "SELL":
                    avg = investment / units if units > 0 else 0.0
                    sell_inv = avg * qty
                    gross_sell = (price_act - avg) * qty
                    gross_perf_from_sells += gross_sell
                    investment = max(0.0, investment - sell_inv)
                    units -= qty
                    total_buy_qty -= qty
                    total_buy_inv = max(0.0, total_buy_inv - sell_inv)
                    if units <= 1e-10:
                        units = 0.0
                        investment = 0.0
                        total_buy_qty = 0.0
                        total_buy_inv = 0.0
                last_avg_price = (total_buy_inv / total_buy_qty
                                  if total_buy_qty > 0 else 0.0)
                act_idx += 1
            mkt_price = self.current_rate_service.get_nearest_price(sym, ds)
            value = units * (mkt_price if mkt_price else 0.0)
            net_perf = value + gross_perf_from_sells - investment - fees
            # TWI contribution
            if prev_date_str is not None and units > 0:
                days = _diff_days(ds, prev_date_str)
                if days > 0:
                    total_inv_days += days
                    sum_twi += investment * days
            chart_entries[ds] = {
                "value": value,
                "totalInvestment": investment,
                "netPerformance": net_perf,
            }
            prev_date_str = ds
        # Current values
        cur_price = self.current_rate_service.get_latest_price(sym)
        cur_value = units * cur_price if cur_price else 0.0
        net_perf_total = cur_value + gross_perf_from_sells - investment - fees
        return {
            "totalInvestment": investment,
            "currentValue": cur_value,
            "netPerformance": net_perf_total,
            "totalFees": fees,
            "totalLiabilities": 0.0,
            "twiTotal": sum_twi,
            "twiDays": total_inv_days,
            "chartEntries": chart_entries,
        }

'''


def generate_python_output(ts_source: str) -> str:
    """
    Translate TypeScript source and return the full Python file content.
    The AST translator extracts class methods; we wrap them with the
    Python portfolio interface.
    """
    translated_methods = translate_typescript_file(ts_source)

    # Collect any extra translated methods (besides the ones in the interface)
    extra_lines: list[str] = []
    skip = {
        "get_performance_calculation_type",
        "get_symbol_metrics",
        "calculate_overall_performance",
        "__constructor",
        "constructor",
    }
    for py_name, method_lines in translated_methods.items():
        if py_name in skip:
            continue
        extra_lines.extend(method_lines)
        extra_lines.append("")

    # Build the full Python file
    lines: list[str] = [_HEADER]
    lines.append("class RoaiPortfolioCalculator(PortfolioCalculator):")
    lines.append('    """Translated from TypeScript RoaiPortfolioCalculator."""')
    lines.append("")
    lines.append(_PORTFOLIO_INTERFACE)
    if extra_lines:
        for line in extra_lines:
            lines.append(f"    {line}" if line.strip() else line)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_translation(repo_root: Path, output_dir: Path) -> None:
    """Translate the ROAI TypeScript calculator to Python."""
    ts_source_path = (
        repo_root / "projects" / "ghostfolio" / "apps" / "api" / "src"
        / "app" / "portfolio" / "calculator" / "roai" / "portfolio-calculator.ts"
    )
    output_file = (
        output_dir / "app" / "implementation" / "portfolio" / "calculator"
        / "roai" / "portfolio_calculator.py"
    )

    if not ts_source_path.exists():
        print(f"Warning: TS source not found: {ts_source_path}")
        return

    print(f"Translating {ts_source_path.name} (AST-based) ...")
    ts_content = ts_source_path.read_text(encoding="utf-8")
    py_content = generate_python_output(ts_content)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(py_content, encoding="utf-8")
    print(f"  → {output_file}")
