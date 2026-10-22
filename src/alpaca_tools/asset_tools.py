from langchain_core.tools import tool
from alpaca.common.exceptions import APIError

from .client import get_trading_client
from .utils import success, api_error, normalize_symbol


@tool
def get_asset_info(symbol: str) -> dict:
    """
    Get Alpaca information about a stock or ETF.

    Useful for verifying that a ticker exists and whether
    the asset is tradable or fractionable.
    """

    try:
        client = get_trading_client()

        symbol = normalize_symbol(symbol)

        asset = client.get_asset(symbol)

        return success(
            symbol=asset.symbol,
            name=asset.name,
            asset_class=asset.asset_class,
            exchange=asset.exchange,
            status=asset.status,
            tradable=asset.tradable,
            marginable=asset.marginable,
            shortable=asset.shortable,
            easy_to_borrow=asset.easy_to_borrow,
            fractionable=asset.fractionable,
        )

    except APIError as exc:
        return api_error(exc)


@tool
def is_asset_tradable(symbol: str) -> dict:
    """
    Check whether a ticker exists and can currently be traded
    through Alpaca.
    """

    try:
        client = get_trading_client()

        symbol = normalize_symbol(symbol)

        asset = client.get_asset(symbol)

        return success(
            symbol=asset.symbol,
            tradable=asset.tradable,
            fractionable=asset.fractionable,
            status=asset.status,
        )

    except APIError as exc:
        return api_error(exc)