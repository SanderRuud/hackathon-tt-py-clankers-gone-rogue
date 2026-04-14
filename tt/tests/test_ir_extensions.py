"""Round-trip tests for ``ts_to_ir`` / ``ir_to_python`` extensions."""
from __future__ import annotations

import ast

import pytest

from tt.ir_to_python import Xcfg, ir_to_function_def
from tt.parser import parse_typescript
from tt.ts_body_parser import parse_wrapped_method
from tt.ts_to_ir import stmt_block_to_ir


def _lower_method_body(ts_body: str) -> list[dict]:
    """Wrap as ``function __wrap(){...}`` — ``ts_body`` must include the outer ``{ ... }``."""
    _tree, src, blk = parse_wrapped_method(ts_body)
    return stmt_block_to_ir(blk, src)


@pytest.mark.parametrize(
    "snippet,expect_substr",
    [
        ("{ const x = a ? b : c; }", "IfExp"),
        ("{ const x = y ?? z; }", "IfExp"),
        ("{ const x = obj?.p; }", "IfExp"),
        ("{ try { a(); } catch (e) { b(); } }", "Try"),
    ],
)
def test_expr_and_stmt_emit_parseable(snippet: str, expect_substr: str) -> None:
    ir = _lower_method_body(snippet)
    hdr = "def f(self):\n  pass\n"
    mod = ast.parse(hdr)
    fn0 = mod.body[0]
    assert isinstance(fn0, ast.FunctionDef)
    fn = ir_to_function_def("f", fn0.args, ir, Xcfg())
    ast.fix_missing_locations(fn)
    code = ast.unparse(fn)
    assert expect_substr in ast.dump(fn) or expect_substr.lower() in code.lower()
    ast.parse(code)


def test_optional_subscript_emits_ifexp() -> None:
    ir = _lower_method_body("{ const x = a?.[0]; }")
    fn = ir_to_function_def("f", ast.parse("def f(self):\n  pass").body[0].args, ir, Xcfg())
    ast.fix_missing_locations(fn)
    code = ast.unparse(fn)
    assert "None" in code


def test_map_comp_list_comp() -> None:
    ir = _lower_method_body("{ const r = arr.map((x) => x + 1); }")
    fn = ir_to_function_def("f", ast.parse("def f(self):\n  pass").body[0].args, ir, Xcfg())
    ast.fix_missing_locations(fn)
    code = ast.unparse(fn)
    assert "for x in" in code.replace(" ", "") or "ListComp" in ast.dump(fn)


def test_merge_metadata_has_field_count() -> None:
    from tt.ast_walker import merge_metadata, walk_typescript

    raw = b"class C { private n: number; m(): void { return; } }"
    t = parse_typescript(raw)
    fr = walk_typescript(t, raw, "t.ts")
    m = merge_metadata([fr])
    assert "field_count" in m
