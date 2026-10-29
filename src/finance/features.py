"""Compute financial features from the statements returned by data_fetcher."""

from typing import get_args

from src.finance.schemas import FinancialFeature

ALL_FEATURES: list[str] = list(get_args(FinancialFeature))

FEATURE_UNITS = {
    "revenue_growth": "% year over year",
    "gross_margin": "% of revenue",
    "operating_margin": "% of revenue",
    "net_margin": "% of revenue",
    "return_on_equity": "% (net income / ending equity)",
    "debt_to_equity": "ratio",
    "current_ratio": "ratio",
    "free_cash_flow": "currency units",
    "free_cash_flow_margin": "% of revenue",
    "earnings_growth": "% year over year",
}

# Used when the LLM selection fails. Banks and insurers have no meaningful
# gross margin or current ratio, and utilities carry high debt by nature.
SECTOR_DEFAULT_FEATURES = {
    "Financial Services": [
        "return_on_equity",
        "net_margin",
        "revenue_growth",
        "earnings_growth",
    ],
    "Utilities": [
        "debt_to_equity",
        "return_on_equity",
        "operating_margin",
        "free_cash_flow",
        "revenue_growth",
    ],
    "Real Estate": [
        "debt_to_equity",
        "operating_margin",
        "free_cash_flow",
        "revenue_growth",
    ],
}

DEFAULT_FEATURES = [
    "revenue_growth",
    "operating_margin",
    "net_margin",
    "return_on_equity",
    "free_cash_flow_margin",
    "debt_to_equity",
]


def ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or not denominator:
        return None
    return numerator / denominator


def rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def percent(value: float | None) -> float | None:
    return None if value is None else round(value * 100, 2)


def growth(current: float | None, previous: float | None) -> float | None:
    if current is None or not previous:
        return None
    return percent((current - previous) / abs(previous))


def free_cash_flow(cashflow: dict, period: str) -> float | None:
    value = cashflow.get("Free Cash Flow", {}).get(period)
    if value is not None:
        return value
    operating = cashflow.get("Operating Cash Flow", {}).get(period)
    capex = cashflow.get("Capital Expenditure", {}).get(period)
    if operating is None or capex is None:
        return None
    # yfinance reports capital expenditure as a negative number.
    return operating + capex


def period_features(statements: dict, period: str, previous: str | None) -> dict:
    income = statements.get("income", {})
    balance = statements.get("balance_sheet", {})
    cashflow = statements.get("cashflow", {})

    def value(statement: dict, row: str, at: str | None = period) -> float | None:
        return statement.get(row, {}).get(at) if at else None

    revenue = value(income, "Total Revenue")
    net_income = value(income, "Net Income")
    equity = value(balance, "Stockholders Equity")
    # Ratios on negative equity are misleading, so leave them out.
    if equity is not None and equity <= 0:
        equity = None
    fcf = free_cash_flow(cashflow, period)

    return {
        "revenue_growth": growth(revenue, value(income, "Total Revenue", previous)),
        "gross_margin": percent(ratio(value(income, "Gross Profit"), revenue)),
        "operating_margin": percent(ratio(value(income, "Operating Income"), revenue)),
        "net_margin": percent(ratio(net_income, revenue)),
        "return_on_equity": percent(ratio(net_income, equity)),
        "debt_to_equity": rounded(ratio(value(balance, "Total Debt"), equity)),
        "current_ratio": rounded(
            ratio(value(balance, "Current Assets"), value(balance, "Current Liabilities"))
        ),
        "free_cash_flow": fcf,
        "free_cash_flow_margin": percent(ratio(fcf, revenue)),
        "earnings_growth": growth(net_income, value(income, "Net Income", previous)),
    }


def feature_history(statements: dict, prefix: str = "", lag: int = 1) -> dict:
    """Return {feature: {period_end: value}}.

    Growth compares each period with the period `lag` steps earlier, so
    quarterly growth uses lag=4 to compare with the same quarter last year.
    """
    view = {
        name: statements.get(f"{prefix}{name}", {})
        for name in ("income", "balance_sheet", "cashflow")
    }
    periods = sorted(view["income"].get("Total Revenue", {}))
    history = {feature: {} for feature in ALL_FEATURES}
    for i, period in enumerate(periods):
        previous = periods[i - lag] if i >= lag else None
        for feature, result in period_features(view, period, previous).items():
            if result is not None:
                history[feature][period] = result
    return history


def compute_features(statements: dict) -> dict:
    """Return the latest annual value and the annual and quarterly history of every feature."""
    annual = feature_history(statements)
    quarterly = feature_history(statements, prefix="quarterly_", lag=4)

    periods = sorted(statements.get("income", {}).get("Total Revenue", {}))
    latest = periods[-1] if periods else None
    return {
        "features_period": latest,
        # Only the most recent fiscal year counts as the current value.
        "features": {
            feature: annual[feature].get(latest) if latest else None
            for feature in ALL_FEATURES
        },
        "feature_history": {
            feature: values for feature, values in annual.items() if values
        },
        "quarterly_feature_history": {
            feature: values for feature, values in quarterly.items() if values
        },
    }


def available_features(features: dict) -> list[str]:
    return [feature for feature, value in features.items() if value is not None]


def default_features(sector: str | None, available: list[str]) -> list[str]:
    defaults = SECTOR_DEFAULT_FEATURES.get(sector, DEFAULT_FEATURES)
    selected = [feature for feature in defaults if feature in available]
    return selected or available[:6]
