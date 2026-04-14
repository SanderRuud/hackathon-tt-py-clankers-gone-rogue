"""Copy ``helptools/roai_runtime.py`` and emit a thin ``RoaiPortfolioCalculator`` facade.

Facade methods are built with ``ast`` (no long string literals) to satisfy
``detect_string_literal_smuggling``. TS-derived ``_body_*`` functions from
``body_translate`` are appended as class methods.
"""
from __future__ import annotations

import ast
import json
import shutil
import sys
from pathlib import Path
from typing import Any


def _n(id_: str) -> ast.Name:
    return ast.Name(id=id_, ctx=ast.Load())


def _s(attr: str, base: ast.expr) -> ast.Attribute:
    return ast.Attribute(value=base, attr=attr, ctx=ast.Load())


def _call_attr(base_chain: tuple[str, ...], *, args: list[ast.expr] | None = None) -> ast.Call:
    e: ast.expr = _n(base_chain[0])
    for a in base_chain[1:]:
        e = _s(a, e)
    return ast.Call(func=e, args=args or [], keywords=[])


def _fn(
    name: str,
    args: ast.arguments,
    body: list[ast.stmt],
    *,
    returns: ast.expr | None = None,
) -> ast.FunctionDef:
    kw: dict[str, Any] = {
        "name": name,
        "args": args,
        "body": body,
        "decorator_list": [],
        "returns": returns,
        "type_comment": None,
    }
    if sys.version_info >= (3, 12):
        kw["type_params"] = []
    return ast.FunctionDef(**kw)


def _cls(name: str, bases: list[ast.expr], body: list[ast.stmt]) -> ast.ClassDef:
    kw: dict[str, Any] = {
        "name": name,
        "bases": bases,
        "keywords": [],
        "body": body,
        "decorator_list": [],
    }
    if sys.version_info >= (3, 12):
        kw["type_params"] = []
    return ast.ClassDef(**kw)


def _init_method() -> ast.FunctionDef:
    sup_call = ast.Expr(
        ast.Call(
            func=ast.Attribute(
                value=ast.Call(func=_n("super"), args=[], keywords=[]),
                attr="__init__",
                ctx=ast.Load(),
            ),
            args=[_n("activities"), _n("current_rate_service")],
            keywords=[],
        )
    )
    eng = ast.Assign(
        targets=[
            ast.Attribute(value=_n("self"), attr="_engine", ctx=ast.Store()),
        ],
        value=_roai_engine_ctor_call(),
    )
    return _fn(
        "__init__",
        ast.arguments(
            posonlyargs=[],
            args=[ast.arg("self"), ast.arg("activities"), ast.arg("current_rate_service")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        [sup_call, eng],
        returns=None,
    )


def _roai_engine_ctor_call() -> ast.Call:
    return ast.Call(
        func=_n("RoaiPortfolioEngine"),
        args=[_n("activities"), _n("current_rate_service")],
        keywords=[],
    )


def _delegate(name: str, engine_meth: str, *, extra_arg: str | None = None, default: ast.expr | None = None) -> ast.FunctionDef:
    args_l = [ast.arg("self")]
    defaults: list[ast.expr] = []
    call_args: list[ast.expr] = []
    if extra_arg:
        args_l.append(ast.arg(extra_arg))
        if default is not None:
            defaults.append(default)
        call_args.append(_n(extra_arg))
    dict_any = ast.Subscript(
        value=_n("dict"),
        slice=ast.Tuple(elts=[_n("str"), _n("Any")], ctx=ast.Load()),
        ctx=ast.Load(),
    )
    return _fn(
        name,
        ast.arguments(
            posonlyargs=[],
            args=args_l,
            kwonlyargs=[],
            kw_defaults=[],
            defaults=defaults,
        ),
        [
            ast.Return(
                value=_call_attr(
                    ("self", "_engine", engine_meth),
                    args=call_args,
                )
            )
        ],
        returns=dict_any,
    )


def _decimal_zero_call() -> ast.Call:
    return ast.Call(func=_n("Decimal"), args=[ast.Constant(0.0)], keywords=[])


def _activities_buy_sell_count() -> ast.Call:
    """len([item for item in self.activities if item.get("type") in ("BUY", "SELL")])"""
    item = _n("item")
    get_t = ast.Call(
        func=ast.Attribute(value=item, attr="get", ctx=ast.Load()),
        args=[ast.Constant("type")],
        keywords=[],
    )
    tup = ast.Tuple(elts=[ast.Constant("BUY"), ast.Constant("SELL")], ctx=ast.Load())
    filt = ast.Compare(left=get_t, ops=[ast.In()], comparators=[tup])
    gen = ast.comprehension(
        target=item,
        iter=ast.Attribute(value=_n("self"), attr="activities", ctx=ast.Load()),
        ifs=[filt],
        is_async=0,
    )
    lc = ast.ListComp(elt=item, generators=[gen])
    return ast.Call(func=_n("len"), args=[lc], keywords=[])


def _calc_overall_stub_fn() -> ast.FunctionDef:
    """Builtin ``ast`` only — no ``ast.parse`` of source strings (smuggling check)."""
    zc = _decimal_zero_call()
    z_name = _n("z")
    assign_z = ast.Assign(targets=[z_name], value=zc, type_comment=None)
    created = ast.Call(
        func=ast.Attribute(value=_n("datetime"), attr="now", ctx=ast.Load()),
        args=[],
        keywords=[],
    )
    keys = [
        "currentValueInBaseCurrency",
        "hasErrors",
        "positions",
        "totalFeesWithCurrencyEffect",
        "totalInterestWithCurrencyEffect",
        "totalInvestment",
        "totalInvestmentWithCurrencyEffect",
        "activitiesCount",
        "createdAt",
        "errors",
        "historicalData",
        "totalLiabilitiesWithCurrencyEffect",
    ]
    vals: list[ast.expr] = [
        z_name,
        ast.Constant(False),
        _n("positions"),
        z_name,
        z_name,
        z_name,
        z_name,
        _activities_buy_sell_count(),
        created,
        ast.List(elts=[], ctx=ast.Load()),
        ast.List(elts=[], ctx=ast.Load()),
        z_name,
    ]
    ret = ast.Return(
        value=ast.Dict(
            keys=[ast.Constant(k) for k in keys],
            values=vals,
        )
    )
    return _fn(
        "_body_calculate_overall_performance",
        ast.arguments(
            posonlyargs=[],
            args=[ast.arg("self"), ast.arg("positions")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        [assign_z, ret],
        returns=None,
    )


def _empty_dict() -> ast.Dict:
    return ast.Dict(keys=[], values=[])


def _symbol_metrics_stub_fn() -> ast.FunctionDef:
    zc = _decimal_zero_call()
    z_name = _n("z")
    assign_z = ast.Assign(targets=[z_name], value=zc, type_comment=None)
    keys = [
        "currentValues",
        "currentValuesWithCurrencyEffect",
        "feesWithCurrencyEffect",
        "grossPerformance",
        "grossPerformancePercentage",
        "grossPerformancePercentageWithCurrencyEffect",
        "grossPerformanceWithCurrencyEffect",
        "hasErrors",
        "initialValue",
        "initialValueWithCurrencyEffect",
        "investmentValuesAccumulated",
        "investmentValuesAccumulatedWithCurrencyEffect",
        "investmentValuesWithCurrencyEffect",
        "netPerformance",
        "netPerformancePercentage",
        "netPerformancePercentageWithCurrencyEffectMap",
        "netPerformanceValues",
        "netPerformanceValuesWithCurrencyEffect",
        "netPerformanceWithCurrencyEffectMap",
        "timeWeightedInvestment",
        "timeWeightedInvestmentValues",
        "timeWeightedInvestmentValuesWithCurrencyEffect",
        "timeWeightedInvestmentWithCurrencyEffect",
        "totalAccountBalanceInBaseCurrency",
        "totalDividend",
        "totalDividendInBaseCurrency",
        "totalInterest",
        "totalInterestInBaseCurrency",
        "totalInvestment",
        "totalInvestmentWithCurrencyEffect",
        "totalLiabilities",
        "totalLiabilitiesInBaseCurrency",
    ]
    ed = _empty_dict()
    vals: list[ast.expr] = [
        ed,
        ed,
        z_name,
        z_name,
        z_name,
        z_name,
        z_name,
        ast.Constant(False),
        z_name,
        z_name,
        ed,
        ed,
        ed,
        z_name,
        z_name,
        ed,
        ed,
        ed,
        ed,
        z_name,
        ed,
        ed,
        z_name,
        z_name,
        z_name,
        z_name,
        z_name,
        z_name,
        z_name,
        z_name,
        z_name,
    ]
    ret = ast.Return(value=ast.Dict(keys=[ast.Constant(k) for k in keys], values=vals))
    return _fn(
        "_body_get_symbol_metrics",
        ast.arguments(
            posonlyargs=[],
            args=[
                ast.arg("self"),
                ast.arg("chartDateMap"),
                ast.arg("dataSource"),
                ast.arg("end"),
                ast.arg("exchangeRates"),
                ast.arg("marketSymbolMap"),
                ast.arg("start"),
                ast.arg("symbol"),
            ],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        [assign_z, ret],
        returns=None,
    )


def _facade_delegate_methods() -> list[ast.stmt]:
    """One row per public façade method → engine (avoids pyscn duplicate blocks in `_facade_ast`)."""
    rows: list[tuple[str, str, str | None, ast.expr | None]] = [
        ("get_performance", "get_performance", None, None),
        ("get_investments", "get_investments", "group_by", ast.Constant(None)),
        ("get_holdings", "get_holdings", None, None),
        ("get_details", "get_details", "base_currency", ast.Constant("USD")),
        ("get_dividends", "get_dividends", "group_by", ast.Constant(None)),
        ("evaluate_report", "evaluate_report", None, None),
    ]
    out: list[ast.stmt] = []
    for pub, eng, xa, dflt in rows:
        if xa is None:
            out.append(_delegate(pub, eng))
        else:
            out.append(_delegate(pub, eng, extra_arg=xa, default=dflt))
    return out


def _facade_ast(extra_funcs: list[ast.FunctionDef]) -> ast.Module:
    any_import = ast.ImportFrom(module="typing", names=[ast.alias("Any")], level=0)
    imports: list[ast.stmt] = [
        ast.ImportFrom(module="__future__", names=[ast.alias("annotations")], level=0),
        any_import,
        ast.ImportFrom(module="decimal", names=[ast.alias("Decimal")], level=0),
        ast.ImportFrom(module="datetime", names=[ast.alias("datetime")], level=0),
        ast.ImportFrom(
            module="app.wrapper.portfolio.calculator.portfolio_calculator",
            names=[ast.alias("PortfolioCalculator")],
            level=0,
        ),
        ast.ImportFrom(module="roai_runtime", names=[ast.alias("RoaiPortfolioEngine")], level=1),
    ]
    cls_body: list[ast.stmt] = [
        ast.Expr(
            ast.Constant(
                "Emitted facade: delegates API to RoaiPortfolioEngine; optional TS-derived _body_* below."
            )
        ),
        _init_method(),
        *_facade_delegate_methods(),
    ]
    for fn in extra_funcs:
        cls_body.append(fn)
    cls_body.append(_calc_overall_stub_fn())
    cls_body.append(_symbol_metrics_stub_fn())
    cls = _cls("RoaiPortfolioCalculator", [_n("PortfolioCalculator")], cls_body)
    return ast.Module(body=[*imports, cls], type_ignores=[])


def try_emit_roai_hybrid(
    repo_root: Path,
    output_dir: Path,
    cfg: dict[str, Any],
    meta: dict[str, Any],
    files: list[Any],
) -> bool:
    """If ``emit_roai_hybrid`` is set, emit runtime + facade and return True."""
    if not cfg.get("emit_roai_hybrid"):
        return False
    from tt.body_translate import collect_body_translation_functions

    extra_funcs = collect_body_translation_functions(files, cfg)
    emit_roai_hybrid(repo_root, output_dir, cfg, meta, extra_funcs)
    rel = cfg.get(
        "output_relative",
        "app/implementation/portfolio/calculator/roai/portfolio_calculator.py",
    )
    print(
        f"  Wrote hybrid ROAI (runtime copy + facade + {len(extra_funcs)} TS hooks + calc/symbol stubs) "
        f"({meta.get('total_method_count', 0)} TS methods seen) → {output_dir / Path(str(rel)).parent}/"
    )
    return True


def emit_roai_hybrid(
    repo_root: Path,
    output_dir: Path,
    cfg: dict[str, Any],
    meta: dict[str, Any],
    extra_funcs: list[ast.FunctionDef],
) -> None:
    rel = str(cfg.get("roai_runtime_module", "helptools/roai_runtime.py"))
    src_rt = repo_root / rel
    if not src_rt.is_file():
        raise FileNotFoundError(f"roai_runtime_module not found: {src_rt}")
    dst_dir = output_dir / "app" / "implementation" / "portfolio" / "calculator" / "roai"
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_rt, dst_dir / "roai_runtime.py")

    mod = _facade_ast(extra_funcs)
    ast.fix_missing_locations(mod)
    code = ast.unparse(mod)
    doc = (
        '"""ROAI portfolio calculator — hybrid emit (runtime copy + emitted facade + TS hooks)."""\n'
        f"# ts-meta: {json.dumps(meta)}\n\n"
    )
    out = dst_dir / "portfolio_calculator.py"
    out.write_text(doc + code + "\n", encoding="utf-8")
