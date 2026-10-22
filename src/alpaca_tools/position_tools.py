from langchain_core.tools import tool
from alpaca.common.exceptions import APIError
from alpaca.trading.requests import ClosePositionRequest

from .client import get_trading_client
from .utils import success, api_error, normalize_symbol


@tool
def get_all_positions() -> dict:
    """
    Get all currently open positions in the portfolio.

    Returns quantities, prices, market values and unrealized P/L.
    """

    try:
        client = get_trading_client()

        positions = client.get_all_positions()

        result = []

        for position in positions:
            result.append(
                {
                    "symbol": position.symbol,
                    "qty": position.qty,
                    "side": position.side,
                    "avg_entry_price": position.avg_entry_price,
                    "current_price": position.current_price,
                    "market_value": position.market_value,
                    "cost_basis": position.cost_basis,
                    "unrealized_pl": position.unrealized_pl,
                    "unrealized_plpc": position.unrealized_plpc,
                    "change_today": position.change_today,
                }
            )

        return success(
            positions=result,
            position_count=len(result),
        )

    except APIError as exc:
        return api_error(exc)


@tool
def get_open_position(symbol: str) -> dict:
    """
    Get the currently open position for one ticker.
    """

    try:
        client = get_trading_client()

        symbol = normalize_symbol(symbol)

        position = client.get_open_position(symbol)

        return success(
            position={
                "symbol": position.symbol,
                "qty": position.qty,
                "side": position.side,
                "avg_entry_price": position.avg_entry_price,
                "current_price": position.current_price,
                "market_value": position.market_value,
                "cost_basis": position.cost_basis,
                "unrealized_pl": position.unrealized_pl,
                "unrealized_plpc": position.unrealized_plpc,
                "change_today": position.change_today,
            }
        )

    except APIError as exc:
        return api_error(exc)


@tool
def close_position(
    symbol: str,
    qty: float | None = None,
    percentage: float | None = None,
) -> dict:
    """
    Close all or part of an existing position.

    Supply either:
        qty=5

    or:
        percentage=50

    Leave both empty to close the entire position.
    """

    if qty is not None and percentage is not None:
        raise ValueError(
            "Specify either qty or percentage, not both."
        )

    if qty is not None and qty <= 0:
        raise ValueError("qty must be greater than 0.")

    if percentage is not None:
        if percentage <= 0 or percentage > 100:
            raise ValueError(
                "percentage must be greater than 0 and at most 100."
            )

    try:
        client = get_trading_client()

        symbol = normalize_symbol(symbol)

        close_options = None

        if qty is not None:
            close_options = ClosePositionRequest(
                qty=str(qty),
            )

        elif percentage is not None:
            close_options = ClosePositionRequest(
                percentage=str(percentage),
            )

        order = client.close_position(
            symbol_or_asset_id=symbol,
            close_options=close_options,
        )

        return success(
            order=order,
        )

    except APIError as exc:
        return api_error(exc)


@tool
def close_all_positions(
    cancel_orders: bool = True,
) -> dict:
    """
    EMERGENCY TOOL.

    Close every currently open position.

    If cancel_orders=True, outstanding open orders are cancelled first.
    """

    try:
        client = get_trading_client()

        responses = client.close_all_positions(
            cancel_orders=cancel_orders,
        )

        return success(
            responses=responses,
        )

    except APIError as exc:
        return api_error(exc)