"""ROAI portfolio calculator — hybrid emit (runtime copy + emitted facade + TS hooks)."""
# ts-meta: {"class_names": ["RoaiPortfolioCalculator"], "total_method_count": 3, "file_count": 2}

from __future__ import annotations
from typing import Any
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
        currentValueInBaseCurrency = Decimal(0.0)
        grossPerformance = Decimal(0.0)
        grossPerformanceWithCurrencyEffect = Decimal(0.0)
        hasErrors = False
        netPerformance = Decimal(0.0)
        totalFeesWithCurrencyEffect = Decimal(0.0)
        totalInterestWithCurrencyEffect = Decimal(0.0)
        totalInvestment = Decimal(0.0)
        totalInvestmentWithCurrencyEffect = Decimal(0.0)
        totalTimeWeightedInvestment = Decimal(0.0)
        totalTimeWeightedInvestmentWithCurrencyEffect = Decimal(0.0)
        for currentPosition in [item for item in positions if item['includeInTotalAssetValue']]:
            if currentPosition.feeInBaseCurrency:
                totalFeesWithCurrencyEffect = totalFeesWithCurrencyEffect + currentPosition.feeInBaseCurrency
            if currentPosition.valueInBaseCurrency:
                currentValueInBaseCurrency = currentValueInBaseCurrency + currentPosition.valueInBaseCurrency
            else:
                hasErrors = True
            if currentPosition.investment:
                totalInvestment = totalInvestment + currentPosition.investment
                totalInvestmentWithCurrencyEffect = totalInvestmentWithCurrencyEffect + currentPosition.investmentWithCurrencyEffect
            else:
                hasErrors = True
            if currentPosition.grossPerformance:
                grossPerformance = grossPerformance + currentPosition.grossPerformance
                grossPerformanceWithCurrencyEffect = grossPerformanceWithCurrencyEffect + currentPosition.grossPerformanceWithCurrencyEffect
                netPerformance = netPerformance + currentPosition.netPerformance
            elif not currentPosition.quantity == 0.0:
                hasErrors = True
            if currentPosition.timeWeightedInvestment:
                totalTimeWeightedInvestment = totalTimeWeightedInvestment + currentPosition.timeWeightedInvestment
                totalTimeWeightedInvestmentWithCurrencyEffect = totalTimeWeightedInvestmentWithCurrencyEffect + currentPosition.timeWeightedInvestmentWithCurrencyEffect
            elif not currentPosition.quantity == 0.0:
                hasErrors = True
        return {'currentValueInBaseCurrency': currentValueInBaseCurrency, 'hasErrors': hasErrors, 'positions': positions, 'totalFeesWithCurrencyEffect': totalFeesWithCurrencyEffect, 'totalInterestWithCurrencyEffect': totalInterestWithCurrencyEffect, 'totalInvestment': totalInvestment, 'totalInvestmentWithCurrencyEffect': totalInvestmentWithCurrencyEffect, 'activitiesCount': len([item for item in self.activities if item['type'] in ('BUY', 'SELL')]), 'createdAt': datetime.now(), 'errors': [], 'historicalData': [], 'totalLiabilitiesWithCurrencyEffect': Decimal(0.0)}

    def _body_get_symbol_metrics(self, chartDateMap, dataSource, end, exchangeRates, marketSymbolMap, start, symbol):
        currentExchangeRate = exchangeRates[format(datetime.now(), DATE_FORMAT)]
        currentValues = {}
        currentValuesWithCurrencyEffect = {}
        fees = Decimal(0.0)
        feesAtStartDate = Decimal(0.0)
        feesAtStartDateWithCurrencyEffect = Decimal(0.0)
        feesWithCurrencyEffect = Decimal(0.0)
        grossPerformance = Decimal(0.0)
        grossPerformanceWithCurrencyEffect = Decimal(0.0)
        grossPerformanceAtStartDate = Decimal(0.0)
        grossPerformanceAtStartDateWithCurrencyEffect = Decimal(0.0)
        grossPerformanceFromSells = Decimal(0.0)
        grossPerformanceFromSellsWithCurrencyEffect = Decimal(0.0)
        initialValue = None
        initialValueWithCurrencyEffect = None
        investmentAtStartDate = None
        investmentAtStartDateWithCurrencyEffect = None
        investmentValuesAccumulated = {}
        investmentValuesAccumulatedWithCurrencyEffect = {}
        investmentValuesWithCurrencyEffect = {}
        lastAveragePrice = Decimal(0.0)
        lastAveragePriceWithCurrencyEffect = Decimal(0.0)
        netPerformanceValues = {}
        netPerformanceValuesWithCurrencyEffect = {}
        timeWeightedInvestmentValues = {}
        timeWeightedInvestmentValuesWithCurrencyEffect = {}
        totalAccountBalanceInBaseCurrency = Decimal(0.0)
        totalDividend = Decimal(0.0)
        totalDividendInBaseCurrency = Decimal(0.0)
        totalInterest = Decimal(0.0)
        totalInterestInBaseCurrency = Decimal(0.0)
        totalInvestment = Decimal(0.0)
        totalInvestmentFromBuyTransactions = Decimal(0.0)
        totalInvestmentFromBuyTransactionsWithCurrencyEffect = Decimal(0.0)
        totalInvestmentWithCurrencyEffect = Decimal(0.0)
        totalLiabilities = Decimal(0.0)
        totalLiabilitiesInBaseCurrency = Decimal(0.0)
        totalQuantityFromBuyTransactions = Decimal(0.0)
        totalUnits = Decimal(0.0)
        valueAtStartDate = None
        valueAtStartDateWithCurrencyEffect = None
        '<unsupported:raw>'
        orders = deepcopy(self.activities.filter(None))
        isCash = orders[0.0].SymbolProfile.assetSubClass == 'CASH'
        if len(orders) <= 0.0:
            return {'currentValues': {}, 'currentValuesWithCurrencyEffect': {}, 'feesWithCurrencyEffect': Decimal(0.0), 'grossPerformance': Decimal(0.0), 'grossPerformancePercentage': Decimal(0.0), 'grossPerformancePercentageWithCurrencyEffect': Decimal(0.0), 'grossPerformanceWithCurrencyEffect': Decimal(0.0), 'hasErrors': False, 'initialValue': Decimal(0.0), 'initialValueWithCurrencyEffect': Decimal(0.0), 'investmentValuesAccumulated': {}, 'investmentValuesAccumulatedWithCurrencyEffect': {}, 'investmentValuesWithCurrencyEffect': {}, 'netPerformance': Decimal(0.0), 'netPerformancePercentage': Decimal(0.0), 'netPerformancePercentageWithCurrencyEffectMap': {}, 'netPerformanceValues': {}, 'netPerformanceValuesWithCurrencyEffect': {}, 'netPerformanceWithCurrencyEffectMap': {}, 'timeWeightedInvestment': Decimal(0.0), 'timeWeightedInvestmentValues': {}, 'timeWeightedInvestmentValuesWithCurrencyEffect': {}, 'timeWeightedInvestmentWithCurrencyEffect': Decimal(0.0), 'totalAccountBalanceInBaseCurrency': Decimal(0.0), 'totalDividend': Decimal(0.0), 'totalDividendInBaseCurrency': Decimal(0.0), 'totalInterest': Decimal(0.0), 'totalInterestInBaseCurrency': Decimal(0.0), 'totalInvestment': Decimal(0.0), 'totalInvestmentWithCurrencyEffect': Decimal(0.0), 'totalLiabilities': Decimal(0.0), 'totalLiabilitiesInBaseCurrency': Decimal(0.0)}
        dateOfFirstTransaction = datetime.now()
        endDateString = format(end, DATE_FORMAT)
        startDateString = format(start, DATE_FORMAT)
        unitPriceAtStartDate = marketSymbolMap[startDateString][symbol]
        unitPriceAtEndDate = marketSymbolMap[endDateString][symbol]
        latestActivity = orders.at(None)
        if ((dataSource == 'MANUAL' and latestActivity.type in ['BUY', 'SELL']) and latestActivity.unitPrice) and (not unitPriceAtEndDate):
            '<unsupported:raw>'
            '<unsupported:raw>'
            unitPriceAtEndDate = latestActivity.unitPrice
        elif isCash:
            unitPriceAtEndDate = Decimal(1.0)
        if not unitPriceAtEndDate or (not unitPriceAtStartDate and isBefore(dateOfFirstTransaction, start)):
            return {'currentValues': {}, 'currentValuesWithCurrencyEffect': {}, 'feesWithCurrencyEffect': Decimal(0.0), 'grossPerformance': Decimal(0.0), 'grossPerformancePercentage': Decimal(0.0), 'grossPerformancePercentageWithCurrencyEffect': Decimal(0.0), 'grossPerformanceWithCurrencyEffect': Decimal(0.0), 'hasErrors': True, 'initialValue': Decimal(0.0), 'initialValueWithCurrencyEffect': Decimal(0.0), 'investmentValuesAccumulated': {}, 'investmentValuesAccumulatedWithCurrencyEffect': {}, 'investmentValuesWithCurrencyEffect': {}, 'netPerformance': Decimal(0.0), 'netPerformancePercentage': Decimal(0.0), 'netPerformancePercentageWithCurrencyEffectMap': {}, 'netPerformanceWithCurrencyEffectMap': {}, 'netPerformanceValues': {}, 'netPerformanceValuesWithCurrencyEffect': {}, 'timeWeightedInvestment': Decimal(0.0), 'timeWeightedInvestmentValues': {}, 'timeWeightedInvestmentValuesWithCurrencyEffect': {}, 'timeWeightedInvestmentWithCurrencyEffect': Decimal(0.0), 'totalAccountBalanceInBaseCurrency': Decimal(0.0), 'totalDividend': Decimal(0.0), 'totalDividendInBaseCurrency': Decimal(0.0), 'totalInterest': Decimal(0.0), 'totalInterestInBaseCurrency': Decimal(0.0), 'totalInvestment': Decimal(0.0), 'totalInvestmentWithCurrencyEffect': Decimal(0.0), 'totalLiabilities': Decimal(0.0), 'totalLiabilitiesInBaseCurrency': Decimal(0.0)}
        '<unsupported:raw>'
        lastUnitPrice = None
        ordersByDate = {}
        for order in orders:
            pass
        if not self.chartDates:
            pass
        for dateString in self.chartDates:
            if dateString < startDateString:
                continue
            elif dateString > endDateString:
                break
            if len(ordersByDate[dateString]) > 0.0:
                for order in ordersByDate[dateString]:
                    pass
            latestActivity = orders.at(None)
            lastUnitPrice = latestActivity.unitPriceFromMarketData + latestActivity.unitPrice
        '<unsupported:raw>'
        '<unsupported:raw>'
        orders = sortBy(orders, None)
        indexOfStartOrder = orders.findIndex(None)
        indexOfEndOrder = orders.findIndex(None)
        totalInvestmentDays = 0.0
        sumOfTimeWeightedInvestments = Decimal(0.0)
        sumOfTimeWeightedInvestmentsWithCurrencyEffect = Decimal(0.0)
        '<unsupported:raw>'
        totalGrossPerformance = grossPerformance - grossPerformanceAtStartDate
        totalGrossPerformanceWithCurrencyEffect = grossPerformanceWithCurrencyEffect - grossPerformanceAtStartDateWithCurrencyEffect
        totalNetPerformance = grossPerformance - grossPerformanceAtStartDate - (fees - feesAtStartDate)
        timeWeightedAverageInvestmentBetweenStartAndEndDate = None
        timeWeightedAverageInvestmentBetweenStartAndEndDateWithCurrencyEffect = None
        grossPerformancePercentage = None
        grossPerformancePercentageWithCurrencyEffect = None
        feesPerUnit = None
        feesPerUnitWithCurrencyEffect = None
        netPerformancePercentage = None
        netPerformancePercentageWithCurrencyEffectMap = {}
        netPerformanceWithCurrencyEffectMap = {}
        for dateRange in None:
            dateInterval = getIntervalFromDateRange(dateRange)
            endDate = dateInterval.endDate
            startDate = dateInterval.startDate
            if isBefore(startDate, start):
                startDate = start
            rangeEndDateString = format(endDate, DATE_FORMAT)
            rangeStartDateString = format(startDate, DATE_FORMAT)
            currentValuesAtDateRangeStartWithCurrencyEffect = currentValuesWithCurrencyEffect[rangeStartDateString] + Decimal(0.0)
            investmentValuesAccumulatedAtStartDateWithCurrencyEffect = investmentValuesAccumulatedWithCurrencyEffect[rangeStartDateString] + Decimal(0.0)
            grossPerformanceAtDateRangeStartWithCurrencyEffect = currentValuesAtDateRangeStartWithCurrencyEffect - investmentValuesAccumulatedAtStartDateWithCurrencyEffect
            average = Decimal(0.0)
            dayCount = 0.0
            '<unsupported:raw>'
            if dayCount > 0.0:
                average = average / dayCount
        if PortfolioCalculator.ENABLE_LOGGING:
            pass
        return {'currentValues': currentValues, 'currentValuesWithCurrencyEffect': currentValuesWithCurrencyEffect, 'feesWithCurrencyEffect': feesWithCurrencyEffect, 'grossPerformancePercentage': grossPerformancePercentage, 'grossPerformancePercentageWithCurrencyEffect': grossPerformancePercentageWithCurrencyEffect, 'initialValue': initialValue, 'initialValueWithCurrencyEffect': initialValueWithCurrencyEffect, 'investmentValuesAccumulated': investmentValuesAccumulated, 'investmentValuesAccumulatedWithCurrencyEffect': investmentValuesAccumulatedWithCurrencyEffect, 'investmentValuesWithCurrencyEffect': investmentValuesWithCurrencyEffect, 'netPerformancePercentage': netPerformancePercentage, 'netPerformancePercentageWithCurrencyEffectMap': netPerformancePercentageWithCurrencyEffectMap, 'netPerformanceValues': netPerformanceValues, 'netPerformanceValuesWithCurrencyEffect': netPerformanceValuesWithCurrencyEffect, 'netPerformanceWithCurrencyEffectMap': netPerformanceWithCurrencyEffectMap, 'timeWeightedInvestmentValues': timeWeightedInvestmentValues, 'timeWeightedInvestmentValuesWithCurrencyEffect': timeWeightedInvestmentValuesWithCurrencyEffect, 'totalAccountBalanceInBaseCurrency': totalAccountBalanceInBaseCurrency, 'totalDividend': totalDividend, 'totalDividendInBaseCurrency': totalDividendInBaseCurrency, 'totalInterest': totalInterest, 'totalInterestInBaseCurrency': totalInterestInBaseCurrency, 'totalInvestment': totalInvestment, 'totalInvestmentWithCurrencyEffect': totalInvestmentWithCurrencyEffect, 'totalLiabilities': totalLiabilities, 'totalLiabilitiesInBaseCurrency': totalLiabilitiesInBaseCurrency, 'grossPerformance': totalGrossPerformance, 'grossPerformanceWithCurrencyEffect': totalGrossPerformanceWithCurrencyEffect, 'hasErrors': totalUnits.gt(0.0) and (not initialValue or not unitPriceAtEndDate), 'netPerformance': totalNetPerformance, 'timeWeightedInvestment': timeWeightedAverageInvestmentBetweenStartAndEndDate, 'timeWeightedInvestmentWithCurrencyEffect': timeWeightedAverageInvestmentBetweenStartAndEndDateWithCurrencyEffect}
