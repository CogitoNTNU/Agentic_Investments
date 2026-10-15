from langchain_core.tools import tool
from alpaca.common.exceptions import APIError
from alpaca.trading.requests import GetPortfolioHistoryRequest

from .client import get_trading_client
from .utils import success, api_error


@tool
def get_account_info() -> dict:
    """
    Get the current Alpaca paper trading account status,
    cash, buying power, equity and portfolio value.

    Use this before making portfolio allocation decisions.
    """

    try:
        client = get_trading_client()
        account = client.get_account()

        return success(
            status=account.status,
            cash=account.cash,
            buying_power=account.buying_power,
            equity=account.equity,
            last_equity=account.last_equity,
            portfolio_value=account.portfolio_value,
            long_market_value=account.long_market_value,
            short_market_value=account.short_market_value,
            initial_margin=account.initial_margin,
            maintenance_margin=account.maintenance_margin,
            trading_blocked=account.trading_blocked,
            account_blocked=account.account_blocked,
            pattern_day_trader=account.pattern_day_trader,
        )

    except APIError as exc:
        return api_error(exc)


@tool
def get_portfolio_history(
    period: str = "1M",
    timeframe: str = "1D",
) -> dict:
    """
    Get historical portfolio equity and P/L.

    Examples:
        period="1D"
        period="1W"
        period="1M"
        period="3M"

    Typical timeframe:
        "1D"
        "1H"
        "15Min"
    """

    try:
        client = get_trading_client()

        request = GetPortfolioHistoryRequest(
            period=period,
            timeframe=timeframe,
        )

        history = client.get_portfolio_history(request)

        return success(
            portfolio_history=history,
        )

    except APIError as exc:
        return api_error(exc)