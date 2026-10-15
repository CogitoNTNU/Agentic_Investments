from langchain_core.tools import tool 

def safe_divide(numerator: float, denominator: float) -> float: 
    if (denominator == 0): 
        raise ValueError("Denominator cannot be zero.")

    return numerator / denominator

@tool 
def calculate_growth_rate(current_value: float, previous_value: float) -> dict:
    """
    Calculate percentage growth from a previous value to a current value. 

    Parameters: 
    Current_value: float 
    Previous_value: float
    """

    growth = (safe_divide(current_value - previous_value, abs(previous_value)) * 100)

    return{
        "growth_rate_pct": round(growth, 2)
    }

@tool 
def calculate_cagr(beginning_value: float, ending_value: float, years: float) -> dict: 
    """Calculate compound annual growth rate (CAGR).
    
    Parameters: 
    Beginning_value: float 
    Ending_value: float 
    Years: float 
    """

    if beginning_value <= 0:
        raise ValueError("Beginning value must be larger than zero.")

    if years <= 0: 
        raise ValueError("Years must be positive.")

    cagr = (
        (ending_value / beginning_value)**(1-years) - 1
        )*100 

    return {
        "cagr_pct": round(cagr, 2)
    }

@tool
def calculate_profitability_ratios(
    revenue: float,
    operating_income: float,
    net_income: float
) -> dict:
    """
    Calculate operating margin and net profit margin.

    Parameters: 
    Revenue: float 
    Operating_income: float 
    Net_income: float 
    """

    operating_margin = (
        safe_divide(
            operating_income,
            revenue
        )
        * 100
    )

    net_margin = (
        safe_divide(
            net_income,
            revenue
        )
        * 100
    )

    return {
        "operating_margin_pct": round(
            operating_margin,
            2
        ),
        "net_margin_pct": round(
            net_margin,
            2
        )
    }


@tool
def calculate_liquidity_ratios(
    current_assets: float,
    current_liabilities: float,
    cash: float = 0,
    receivables: float = 0
) -> dict:
    """
    Calculate current ratio and simplified quick ratio.

    Parameters: 
    Current_assets: float 
    Current_liabilities: float 
    Cash: float 
    Receivables: float 
    """

    current_ratio = safe_divide(
        current_assets,
        current_liabilities
    )

    quick_ratio = safe_divide(
        cash + receivables,
        current_liabilities
    )

    return {
        "current_ratio": round(
            current_ratio,
            2
        ),
        "quick_ratio": round(
            quick_ratio,
            2
        )
    }


@tool
def calculate_leverage_ratios(
    total_debt: float,
    total_equity: float,
    cash: float = 0,
    ebitda: float = 0
) -> dict:
    """
    Calculate debt-to-equity and optionally
    net-debt-to-EBITDA.

    Parameters: 
    Total_debt: float 
    Total_equity: Float 
    Cash: float 
    Ebitda: float
    """

    debt_to_equity = safe_divide(
        total_debt,
        total_equity
    )

    result = {
        "debt_to_equity": round(
            debt_to_equity,
            2
        )
    }

    if ebitda != 0:

        net_debt = (
            total_debt - cash
        )

        net_debt_to_ebitda = safe_divide(
            net_debt,
            ebitda
        )

        result["net_debt_to_ebitda"] = round(
            net_debt_to_ebitda,
            2
        )

    return result


@tool
def calculate_free_cash_flow(
    operating_cash_flow: float,
    capital_expenditures: float,
    revenue: float = 0
) -> dict:
    """
    Calculate free cash flow.

    Capital expenditures should be given as
    a positive number representing cash spent.

    Parameters: 
    Operating_cash_flow: float 
    Capital_expenditures: float 
    Revenue: float 
    """

    free_cash_flow = (
        operating_cash_flow
        - capital_expenditures
    )

    result = {
        "free_cash_flow": round(
            free_cash_flow,
            2
        )
    }

    if revenue != 0:

        fcf_margin = (
            safe_divide(
                free_cash_flow,
                revenue
            )
            * 100
        )

        result["fcf_margin_pct"] = round(
            fcf_margin,
            2
        )

    return result


@tool
def calculate_return_on_equity(
    net_income: float,
    average_equity: float
) -> dict:
    """
    Calculate return on equity (ROE).

    Parameters: 
    Net_income: float 
    Average_equity: float
    """

    roe = (
        safe_divide(
            net_income,
            average_equity
        )
        * 100
    )

    return {
        "roe_pct": round(
            roe,
            2
        )
    }


@tool
def calculate_interest_coverage(
    operating_income: float,
    interest_expense: float
) -> dict:
    """
    Calculate interest coverage ratio.

    Parameters: 
    Operating_income: float
    Interest_expense: float
    """

    coverage = safe_divide(
        operating_income,
        interest_expense
    )

    return {
        "interest_coverage": round(
            coverage,
            2
        )
    }


@tool
def project_compound_growth(
    current_value: float,
    growth_rate_pct: float,
    periods: int
) -> dict:
    """
    Project a financial value forward assuming
    a constant compound growth rate.

    Only use growth assumptions supported by
    report data or company guidance.

    Parameters: 
    Current_value: float 
    Growth_rate_pct: float 
    Periods: float
    """

    if periods <= 0:
        raise ValueError(
            "Periods must be positive."
        )

    values = []

    value = current_value

    for period in range(
        1,
        periods + 1
    ):

        value = value * (
            1 + growth_rate_pct / 100
        )

        values.append({
            "period": period,
            "projected_value": round(
                value,
                2
            )
        })

    return {
        "growth_rate_pct": growth_rate_pct,
        "projections": values
    }

@tool
def forecast_linear_trend(
    values: list[float],
    periods_ahead: int = 4
) -> dict:
    """
    Fit a simple linear trend to historical
    financial values and extrapolate future values.

    This is a mechanical trend forecast and should
    not be interpreted as a guaranteed prediction.
    """

    if len(values) < 2:
        raise ValueError(
            "At least two historical values are required."
        )

    if periods_ahead <= 0:
        raise ValueError(
            "periods_ahead must be positive."
        )

    n = len(values)

    x_values = list(
        range(n)
    )

    x_mean = sum(
        x_values
    ) / n

    y_mean = sum(
        values
    ) / n

    numerator = sum(
        (x - x_mean) * (y - y_mean)
        for x, y in zip(
            x_values,
            values
        )
    )

    denominator = sum(
        (x - x_mean) ** 2
        for x in x_values
    )

    slope = safe_divide(
        numerator,
        denominator
    )

    intercept = (
        y_mean
        - slope * x_mean
    )

    fitted_values = [
        intercept + slope * x
        for x in x_values
    ]

    ss_residual = sum(
        (actual - fitted) ** 2
        for actual, fitted in zip(
            values,
            fitted_values
        )
    )

    ss_total = sum(
        (actual - y_mean) ** 2
        for actual in values
    )

    if ss_total == 0:
        r_squared = 1.0

    else:
        r_squared = (
            1
            - ss_residual / ss_total
        )

    forecasts = []

    for step in range(
        1,
        periods_ahead + 1
    ):

        future_x = (
            n - 1 + step
        )

        prediction = (
            intercept
            + slope * future_x
        )

        forecasts.append({
            "period_ahead": step,
            "forecast": round(
                prediction,
                2
            )
        })

    return {
        "slope_per_period": round(
            slope,
            4
        ),
        "r_squared": round(
            r_squared,
            4
        ),
        "forecasts": forecasts
    }


FINANCIAL_TOOLS = [
    calculate_growth_rate,
    calculate_cagr,
    calculate_profitability_ratios,
    calculate_liquidity_ratios,
    calculate_leverage_ratios,
    calculate_free_cash_flow,
    calculate_return_on_equity,
    calculate_interest_coverage,
    project_compound_growth,
    forecast_linear_trend
]