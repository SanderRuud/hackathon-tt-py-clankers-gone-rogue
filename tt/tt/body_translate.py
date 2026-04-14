"""Glue: TS method body text → Python ast.FunctionDef (or None on failure)."""
from __future__ import annotations

import ast as py_ast
from typing import Any

from tt.ir_to_python import Xcfg, ir_to_function_def, rewrite_returns_enum_strings
from tt.ts_body_parser import parse_wrapped_method
from tt.ts_to_ir import stmt_block_to_ir


def translate_method_body(
    body_text: str,
    python_name: str,
    params_src: str,
    *,
    decimal_name: str = "Decimal",
) -> py_ast.FunctionDef | None:
    """Try to translate a TS statement_block string into a Python function."""
    try:
        _tree, src, blk = parse_wrapped_method(body_text)
        ir = stmt_block_to_ir(blk, src)
        rewrite_returns_enum_strings(ir)
        hdr = f"def {python_name}{params_src}:\n  pass\n"
        mod = py_ast.parse(hdr)
        fn0 = mod.body[0]
        assert isinstance(fn0, py_ast.FunctionDef)
        cfg = Xcfg(decimal_name=decimal_name)
        fn2 = ir_to_function_def(
            python_name,
            fn0.args,
            ir,
            cfg,
        )
        py_ast.fix_missing_locations(fn2)
        py_ast.parse(py_ast.unparse(fn2))
        return fn2
    except (ValueError, SyntaxError, TypeError, KeyError):
        return None


def find_method_body(files: list[Any], class_name: str, method_name: str) -> str | None:
    """Look up raw body text from FileIR list."""
    for f in files:
        for c in f.classes:
            if c.name != class_name:
                continue
            for m in c.methods:
                if m.name == method_name:
                    return m.body_text
    return None


def collect_body_translation_functions(
    files: list[Any],
    cfg: dict[str, Any],
) -> list[py_ast.FunctionDef]:
    """Emit translated TS method bodies per config `body_translations` (skips on failure)."""
    out: list[py_ast.FunctionDef] = []
    cls_name = str(cfg.get("target_class_name", ""))
    for entry in cfg.get("body_translations") or []:
        ts_name = entry.get("typescript_method") or entry.get("ts_method")
        py_name = entry.get("python_name")
        params_src = entry.get("params_src")
        if not (ts_name and py_name and params_src):
            continue
        body_text = find_method_body(files, cls_name, str(ts_name))
        if not body_text:
            print(f"Warning: TypeScript method body not found: {cls_name}.{ts_name}")
            continue
        fn = translate_method_body(str(body_text), str(py_name), str(params_src))
        if fn is None:
            print(f"Warning: body translation failed for {cls_name}.{ts_name}")
            continue
        out.append(fn)
    return out
