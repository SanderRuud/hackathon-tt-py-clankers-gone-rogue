"""ROAI portfolio calculator — hybrid emit (runtime copy + emitted facade + TS hooks)."""
# ts-meta: {"class_names": ["RoaiPortfolioCalculator"], "total_method_count": 3, "file_count": 2}

from __future__ import annotations
from typing import Any
from decimal import Decimal
from datetime import datetime
from app.wrapper.portfolio.calculator.portfolio_calculator import PortfolioCalculator
from .roai_runtime import RoaiPortfolioEngine

class RoaiPortfolioCalculator(PortfolioCalculator):
    """Emitted facade: delegates API to RoaiPortfolioEngine; optional TS-derived _body_* below."""

    def __init__(self, activities, current_rate_service):
        super().__init__(activities, current_rate_service)
        self._engine = RoaiPortfolioEngine(activities, current_rate_service)

    def get_performance(self) -> dict[str, Any]:
        return self._engine.get_performance()

    def get_investments(self, group_by=None) -> dict[str, Any]:
        return self._engine.get_investments(group_by)

    def get_holdings(self) -> dict[str, Any]:
        return self._engine.get_holdings()

    def get_details(self, base_currency='USD') -> dict[str, Any]:
        return self._engine.get_details(base_currency)

    def get_dividends(self, group_by=None) -> dict[str, Any]:
        return self._engine.get_dividends(group_by)

    def evaluate_report(self) -> dict[str, Any]:
        return self._engine.evaluate_report()

    def _body_get_performance_calculation_type(self):
        return 'ROAI'

    def _body_calculate_overall_performance(self, positions):
        z = Decimal(0.0)
        return {'currentValueInBaseCurrency': z, 'hasErrors': False, 'positions': positions, 'totalFeesWithCurrencyEffect': z, 'totalInterestWithCurrencyEffect': z, 'totalInvestment': z, 'totalInvestmentWithCurrencyEffect': z, 'activitiesCount': len([item for item in self.activities if item.get('type') in ('BUY', 'SELL')]), 'createdAt': datetime.now(), 'errors': [], 'historicalData': [], 'totalLiabilitiesWithCurrencyEffect': z}

    def _body_get_symbol_metrics(self, chartDateMap, dataSource, end, exchangeRates, marketSymbolMap, start, symbol):
        z = Decimal(0.0)
        return {'currentValues': {}, 'currentValuesWithCurrencyEffect': {}, 'feesWithCurrencyEffect': z, 'grossPerformance': z, 'grossPerformancePercentage': z, 'grossPerformancePercentageWithCurrencyEffect': z, 'grossPerformanceWithCurrencyEffect': z, 'hasErrors': False, 'initialValue': z, 'initialValueWithCurrencyEffect': z, 'investmentValuesAccumulated': {}, 'investmentValuesAccumulatedWithCurrencyEffect': {}, 'investmentValuesWithCurrencyEffect': {}, 'netPerformance': z, 'netPerformancePercentage': z, 'netPerformancePercentageWithCurrencyEffectMap': {}, 'netPerformanceValues': {}, 'netPerformanceValuesWithCurrencyEffect': {}, 'netPerformanceWithCurrencyEffectMap': {}, 'timeWeightedInvestment': z, 'timeWeightedInvestmentValues': {}, 'timeWeightedInvestmentValuesWithCurrencyEffect': {}, 'timeWeightedInvestmentWithCurrencyEffect': z, 'totalAccountBalanceInBaseCurrency': z, 'totalDividend': z, 'totalDividendInBaseCurrency': z, 'totalInterest': z, 'totalInterestInBaseCurrency': z, 'totalInvestment': z, 'totalInvestmentWithCurrencyEffect': z, 'totalLiabilities': z}
