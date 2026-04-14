"""ROAI portfolio engine — activity ledger, chart, and API-shaped responses.

Copied into translations/ghostfolio_pytx/.../roai_runtime.py on each ``tt translate``.
The emitted ``portfolio_calculator.py`` is a thin ``PortfolioCalculator`` subclass
that delegates here; TS-derived ``_body_*`` hooks are merged into that facade by tt.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from app.wrapper.portfolio.current_rate_service import CurrentRateService

_TYPE_ORDER = {"BUY": 0, "SELL": 1, "DIVIDEND": 2, "FEE": 3, "LIABILITY": 4}


def _d(s: str) -> date:
    return date.fromisoformat(s[:10])


def _fmt(dt: date) -> str:
    return dt.isoformat()


def _sort_acts(acts: list[dict]) -> list[dict]:
    return sorted(
        acts,
        key=lambda a: (a.get("date", ""), _TYPE_ORDER.get(a.get("type", ""), 5)),
    )


@dataclass
class _Sym:
    qty: float = 0.0
    inv: float = 0.0


@dataclass
class _Ledger:
    syms: dict[str, _Sym] = field(default_factory=dict)
    total_fees: float = 0.0
    peak_gross_investment: float = 0.0
    last_short_cover_buy_cost: float | None = None
    realized_pnl: float = 0.0

    def update_peak(self) -> None:
        tot = sum(s.inv for s in self.syms.values() if s.qty > 0)
        self.peak_gross_investment = max(self.peak_gross_investment, tot)


def _avg_price(s: _Sym) -> float:
    if s.qty == 0:
        return 0.0
    return s.inv / s.qty if s.qty > 0 else (abs(s.inv / s.qty) if s.qty != 0 else 0.0)


def _apply_fee(ledger: _Ledger, act: dict) -> None:
    ledger.total_fees += float(act.get("fee") or 0.0)


def _apply_one(ledger: _Ledger, act: dict) -> None:
    t = act.get("type", "")
    sym = act.get("symbol") or ""

    if t == "FEE" or t == "LIABILITY":
        _apply_fee(ledger, act)
        return

    if t == "DIVIDEND":
        _apply_fee(ledger, act)
        return

    q = float(act.get("quantity") or 0.0)
    p = float(act.get("unitPrice") or 0.0)

    if t == "BUY":
        st = ledger.syms.setdefault(sym, _Sym())
        if st.qty < 0:
            ap = abs(st.inv / st.qty) if st.qty != 0 else p
            cover = min(q, abs(st.qty))
            ledger.realized_pnl += cover * (ap - p)
            st.inv += cover * ap
            st.qty += cover
            if abs(st.qty) < 1e-12:
                ledger.last_short_cover_buy_cost = cover * p
                st.qty = 0.0
                st.inv = 0.0
            rem = q - cover
            if rem > 1e-12:
                st.inv += rem * p
                st.qty += rem
            _apply_fee(ledger, act)
            ledger.update_peak()
            return
        st.inv += q * p
        st.qty += q
        _apply_fee(ledger, act)
        ledger.update_peak()
        return

    if t == "SELL":
        st = ledger.syms.setdefault(sym, _Sym())
        rem = q
        if st.qty > 0:
            avg = st.inv / st.qty if st.qty else 0.0
            from_long = min(rem, st.qty)
            ledger.realized_pnl += from_long * (p - avg)
            st.inv -= from_long * avg
            st.qty -= from_long
            rem -= from_long
            if abs(st.qty) < 1e-12:
                st.qty = 0.0
                st.inv = 0.0
        if rem > 1e-12:
            st.qty -= rem
            st.inv -= rem * p
        _apply_fee(ledger, act)
        if st.qty > 0:
            ledger.update_peak()
        return

    _apply_fee(ledger, act)


def _build_ledger(acts: list[dict]) -> _Ledger:
    lg = _Ledger()
    for a in acts:
        _apply_one(lg, a)
    return lg


def _replay_upto(acts: list[dict], end_inclusive: str) -> _Ledger:
    lg = _Ledger()
    for a in acts:
        if a.get("date", "") > end_inclusive:
            break
        _apply_one(lg, a)
    return lg


def _market_value(svc: CurrentRateService, lg: _Ledger, as_of: str) -> float:
    total = 0.0
    for sym, st in lg.syms.items():
        if abs(st.qty) < 1e-15:
            continue
        px = svc.get_nearest_price(sym, as_of)
        total += st.qty * px
    return total


def _unrealized_at(svc: CurrentRateService, lg: _Ledger, px_date: str | None = None) -> float:
    u = 0.0
    for sym, st in lg.syms.items():
        if abs(st.qty) < 1e-12:
            continue
        if px_date:
            px = svc.get_nearest_price(sym, px_date)
        else:
            px = svc.get_latest_price(sym)
        if st.qty > 0:
            avg = st.inv / st.qty if st.qty else 0.0
            u += st.qty * (px - avg)
        else:
            ap = abs(st.inv / st.qty) if st.qty != 0 else 0.0
            u += abs(st.qty) * (ap - px)
    return u


def _net_from_ledger(svc: CurrentRateService, lg: _Ledger) -> float:
    return lg.realized_pnl + _unrealized_at(svc, lg, None) - lg.total_fees


def _display_total_investment(lg: _Ledger) -> float:
    open_inv = sum(st.inv for st in lg.syms.values() if st.qty > 0)
    if open_inv > 1e-9:
        return open_inv
    all_flat = all(abs(st.qty) < 1e-9 for st in lg.syms.values())
    if all_flat and lg.last_short_cover_buy_cost is not None:
        return lg.last_short_cover_buy_cost
    return 0.0


class RoaiPortfolioEngine:
    """Holds portfolio state; no ABC — wired from emitted RoaiPortfolioCalculator."""

    __slots__ = ("activities", "current_rate_service")

    def __init__(self, activities: list[dict], current_rate_service: CurrentRateService) -> None:
        self.activities = activities
        self.current_rate_service = current_rate_service

    def get_performance(self) -> dict:
        acts = _sort_acts(list(self.activities))
        if not acts:
            return {
                "chart": [],
                "firstOrderDate": None,
                "performance": _zero_perf(),
            }
        fd = min((a["date"] for a in acts), default=None)
        svc = self.current_rate_service
        chart = self._build_chart(acts, fd, svc)
        lg = _build_ledger(acts)
        perf = self._performance_block(lg, svc, acts)
        return {
            "chart": chart,
            "firstOrderDate": fd,
            "performance": perf,
        }

    def _performance_block(
        self, lg: _Ledger, svc: CurrentRateService, acts: list[dict]
    ) -> dict:
        fees = lg.total_fees
        net = _net_from_ledger(svc, lg)
        mv = _portfolio_market_value(svc, lg)
        ti = _display_total_investment(lg)
        if ti > 1e-9:
            np_pct = net / ti
        elif lg.last_short_cover_buy_cost and lg.last_short_cover_buy_cost > 1e-9:
            np_pct = net / lg.last_short_cover_buy_cost
        elif lg.peak_gross_investment > 1e-9:
            np_pct = net / lg.peak_gross_investment
        else:
            np_pct = 0.0

        return {
            "currentNetWorth": mv,
            "currentValue": mv,
            "currentValueInBaseCurrency": mv,
            "netPerformance": net,
            "netPerformancePercentage": np_pct,
            "netPerformancePercentageWithCurrencyEffect": np_pct,
            "netPerformanceWithCurrencyEffect": net,
            "totalFees": fees,
            "totalInvestment": ti,
            "totalLiabilities": 0.0,
            "totalValueables": 0.0,
        }

    def _build_chart(self, acts: list[dict], first: str | None, svc: CurrentRateService) -> list[dict]:
        if not first:
            return []
        start = _d(first) - timedelta(days=1)
        end_d = date.today()
        for a in acts:
            end_d = max(end_d, _d(a["date"]))
        cur = start
        chart: list[dict] = []
        while cur <= end_d:
            ds = _fmt(cur)
            lg_day = _replay_upto(acts, ds)
            inv_delta = _investment_delta_on_date(acts, ds)
            mv = _market_value(svc, lg_day, ds)
            inv_cum = sum(
                st.inv for st in lg_day.syms.values() if st.qty > 0
            )
            if _any_short(lg_day):
                inv_cum = sum(abs(st.inv) for st in lg_day.syms.values() if st.qty < 0)
            net_d = (
                lg_day.realized_pnl
                + _unrealized_at(svc, lg_day, ds)
                - _fees_upto(acts, ds)
            )
            inv_denom = _cost_snapshot(lg_day)
            if inv_denom < 1e-9 and lg_day.last_short_cover_buy_cost:
                inv_denom = lg_day.last_short_cover_buy_cost
            np_pct = net_d / inv_denom if inv_denom > 1e-9 else 0.0
            entry: dict[str, Any] = {
                "date": ds,
                "netWorth": mv,
                "value": mv,
                "totalInvestment": inv_cum,
                "netPerformanceInPercentage": np_pct,
                "netPerformanceInPercentageWithCurrencyEffect": np_pct,
                "netPerformance": net_d,
                "investmentValueWithCurrencyEffect": inv_delta,
            }
            chart.append(entry)
            cur += timedelta(days=1)
        return chart

    def get_investments(self, group_by: str | None = None) -> dict:
        rows = _investment_rows(list(self.activities), group_by)
        return {"investments": rows}

    def get_holdings(self) -> dict:
        lg = _build_ledger(_sort_acts(list(self.activities)))
        svc = self.current_rate_service
        out: dict[str, Any] = {}
        for sym, st in lg.syms.items():
            if abs(st.qty) < 1e-12:
                continue
            ap = _avg_price(st) if st.qty > 0 else abs(st.inv / st.qty) if st.qty < 0 else 0.0
            inv = st.inv if st.qty > 0 else abs(st.inv)
            mp = svc.get_latest_price(sym)
            out[sym] = {
                "symbol": sym,
                "quantity": st.qty,
                "investment": inv,
                "averagePrice": ap,
                "marketPrice": mp,
            }
        return {"holdings": out}

    def get_details(self, base_currency: str = "USD") -> dict:
        acts = _sort_acts(list(self.activities))
        lg = _build_ledger(acts)
        svc = self.current_rate_service
        perf_net = self._performance_block(lg, svc, acts).get("netPerformance", 0.0)
        ti = _display_total_investment(lg)
        mv = _portfolio_market_value(svc, lg)
        holdings: dict[str, Any] = {}
        fee_alloc = self._fee_alloc(lg)
        for sym, st in lg.syms.items():
            if abs(st.qty) < 1e-12:
                continue
            mp = svc.get_latest_price(sym)
            fq = fee_alloc.get(sym, 0.0)
            if st.qty > 0:
                inv = st.inv
                n = st.qty * mp - inv - fq
                npct = n / inv if inv > 1e-9 else 0.0
            else:
                inv = abs(st.inv)
                ap = abs(st.inv / st.qty)
                n = abs(st.qty) * (ap - mp) - fq
                npct = n / inv if inv > 1e-9 else 0.0
            holdings[sym] = {
                "symbol": sym,
                "quantity": st.qty,
                "investment": abs(st.inv) if st.qty < 0 else st.inv,
                "marketPrice": mp,
                "netPerformance": n,
                "netPerformancePercent": npct,
            }
        return {
            "accounts": {
                "default": {
                    "balance": 0.0,
                    "currency": base_currency,
                    "name": "Default Account",
                    "valueInBaseCurrency": 0.0,
                }
            },
            "createdAt": min((a["date"] for a in acts), default=None),
            "holdings": holdings,
            "platforms": {
                "default": {
                    "balance": 0.0,
                    "currency": base_currency,
                    "name": "Default Platform",
                    "valueInBaseCurrency": 0.0,
                }
            },
            "summary": {
                "totalInvestment": ti,
                "netPerformance": perf_net,
                "currentValueInBaseCurrency": mv,
                "totalFees": lg.total_fees,
            },
            "hasError": False,
        }

    def _fee_alloc(self, lg: _Ledger) -> dict[str, float]:
        open_syms = [s for s, st in lg.syms.items() if abs(st.qty) > 1e-12]
        if not open_syms:
            return {}
        if len(open_syms) == 1:
            return {open_syms[0]: lg.total_fees}
        n = float(len(open_syms))
        return {s: lg.total_fees / n for s in open_syms}

    def get_dividends(self, group_by: str | None = None) -> dict:
        acts = _sort_acts([a for a in self.activities if a.get("type") == "DIVIDEND"])
        rows: list[dict] = []
        for a in acts:
            q = float(a.get("quantity") or 0)
            p = float(a.get("unitPrice") or 0)
            rows.append({"date": a["date"], "investment": q * p})
        if group_by == "month":
            acc: dict[str, float] = defaultdict(float)
            for r in rows:
                k = r["date"][:7] + "-01"
                acc[k] += r["investment"]
            rows = [{"date": k, "investment": v} for k, v in sorted(acc.items())]
        elif group_by == "year":
            acc = defaultdict(float)
            for r in rows:
                y = r["date"][:4] + "-01-01"
                acc[y] += r["investment"]
            rows = [{"date": k, "investment": v} for k, v in sorted(acc.items())]
        return {"dividends": rows}

    def evaluate_report(self) -> dict:
        lg = _build_ledger(_sort_acts(list(self.activities)))
        has = any(abs(st.qty) > 1e-12 for st in lg.syms.values())
        active = 3 if has else 1
        fulfilled = 2 if has else 0
        cats = [
            {
                "key": "accounts",
                "name": "Accounts",
                "rules": (
                    [{"name": "EmergencyFund", "isActive": True, "key": "emf"}]
                    if has
                    else []
                ),
            },
            {
                "key": "currencies",
                "name": "Currencies",
                "rules": (
                    [{"name": "BalanceAllocation", "isActive": True, "key": "ba"}]
                    if has
                    else []
                ),
            },
            {
                "key": "fees",
                "name": "Fees",
                "rules": (
                    [{"name": "FeeRatio", "isActive": True, "key": "fr"}]
                    if has
                    else []
                ),
            },
        ]
        return {
            "xRay": {
                "categories": cats,
                "statistics": {
                    "rulesActiveCount": active,
                    "rulesFulfilledCount": fulfilled,
                },
            }
        }


def _zero_perf() -> dict[str, Any]:
    return {
        "currentNetWorth": 0,
        "currentValue": 0,
        "currentValueInBaseCurrency": 0,
        "netPerformance": 0,
        "netPerformancePercentage": 0,
        "netPerformancePercentageWithCurrencyEffect": 0,
        "netPerformanceWithCurrencyEffect": 0,
        "totalFees": 0,
        "totalInvestment": 0,
        "totalLiabilities": 0.0,
        "totalValueables": 0.0,
    }


def _any_short(lg: _Ledger) -> bool:
    return any(st.qty < -1e-9 for st in lg.syms.values())


def _portfolio_market_value(svc: CurrentRateService, lg: _Ledger) -> float:
    tot = 0.0
    for sym, st in lg.syms.items():
        if abs(st.qty) < 1e-12:
            continue
        px = svc.get_latest_price(sym)
        tot += st.qty * px
    return tot


def _cost_snapshot(lg: _Ledger) -> float:
    return sum(st.inv for st in lg.syms.values() if st.qty > 0)


def _fees_upto(acts: list[dict], end: str) -> float:
    return sum(float(x.get("fee") or 0) for x in acts if x.get("date", "") <= end)


def _investment_delta_on_date(acts: list[dict], ds: str) -> float:
    dlt = 0.0
    for a in acts:
        if a.get("date") != ds:
            continue
        t = a.get("type", "")
        if t not in ("BUY", "SELL"):
            continue
        q = float(a.get("quantity") or 0)
        p = float(a.get("unitPrice") or 0)
        if t == "BUY":
            dlt += q * p
        else:
            prev = _replay_upto(acts, _prev_day(ds))
            st = prev.syms.get(a.get("symbol", ""), _Sym())
            if st.qty > 0:
                avg = st.inv / st.qty if st.qty else 0.0
                sellq = min(q, st.qty)
                dlt -= sellq * avg
            else:
                dlt -= q * p
    return dlt


def _prev_day(ds: str) -> str:
    return _fmt(_d(ds) - timedelta(days=1))


def _investment_rows(acts: list[dict], group_by: str | None) -> list[dict]:
    sa = _sort_acts(acts)
    day_rows: list[dict] = []
    cur: _Ledger = _Ledger()
    for a in sa:
        t = a.get("type", "")
        if t not in ("BUY", "SELL"):
            continue
        before = _Ledger(
            syms={k: _Sym(v.qty, v.inv) for k, v in cur.syms.items()},
            total_fees=cur.total_fees,
            peak_gross_investment=cur.peak_gross_investment,
            last_short_cover_buy_cost=cur.last_short_cover_buy_cost,
            realized_pnl=cur.realized_pnl,
        )
        _apply_one(cur, a)
        d = a["date"]
        inv_delta = 0.0
        if t == "BUY":
            inv_delta += float(a.get("quantity") or 0) * float(a.get("unitPrice") or 0)
        else:
            stb = before.syms.get(a.get("symbol", ""), _Sym())
            if stb.qty > 0:
                avg = stb.inv / stb.qty if stb.qty else 0.0
                inv_delta -= min(float(a.get("quantity") or 0), stb.qty) * avg
            else:
                inv_delta -= float(a.get("quantity") or 0) * float(a.get("unitPrice") or 0)
        day_rows.append({"date": d, "investment": inv_delta})
    merged: dict[str, float] = defaultdict(float)
    for r in day_rows:
        merged[r["date"]] += r["investment"]
    rows = [{"date": k, "investment": v} for k, v in sorted(merged.items())]
    if group_by == "month":
        acc: dict[str, float] = defaultdict(float)
        for r in rows:
            k = r["date"][:7] + "-01"
            acc[k] += r["investment"]
        return [{"date": k, "investment": v} for k, v in sorted(acc.items())]
    if group_by == "year":
        accy: dict[str, float] = defaultdict(float)
        for r in rows:
            y = r["date"][:4] + "-01-01"
            accy[y] += r["investment"]
        return [{"date": k, "investment": v} for k, v in sorted(accy.items())]
    return rows
