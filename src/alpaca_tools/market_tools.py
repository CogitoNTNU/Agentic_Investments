from langchain_core.tools import tool
from alpaca.common.exceptions import APIError

from .client import get_trading_client
from .utils import success, api_error


@tool
def get_market_clock() -> dict:
    """
    Get the current US market clock.

    Returns whether the market is open and the timestamps
    for the next market open and close.
    """

    try:
        client = get_trading_client()
        clock = client.get_clock()

        return success(
            is_open=clock.is_open,
            timestamp=clock.timestamp,
            next_open=clock.next_open,
            next_close=clock.next_close,
        )

    except APIError as exc:
        return api_error(exc)