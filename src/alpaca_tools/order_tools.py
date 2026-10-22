from langchain_core.tools import tool

from alpaca.common.exceptions import APIError
from alpaca.trading.enums import (
    OrderClass,
    OrderSide,
    QueryOrderStatus,
    TimeInForce,
)
from alpaca.trading.requests import (
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
    ReplaceOrderRequest,
    StopLimitOrderRequest,
    StopLossRequest,
    StopOrderRequest,
    TakeProfitRequest,
    TrailingStopOrderRequest,
)

from .client import get_trading_client
from .utils import (
    success,
    api_error,
    normalize_symbol,
)


def _parse_side(side: str) -> OrderSide:
    side = side.strip().lower()

    if side == "buy":
        return OrderSide.BUY

    if side == "sell":
        return OrderSide.SELL

    raise ValueError(
        "side must be either 'buy' or 'sell'."
    )


def _parse_time_in_force(
    time_in_force: str,
) -> TimeInForce:
    try:
        return TimeInForce(
            time_in_force.strip().lower()
        )

    except ValueError as exc:
        raise ValueError(
            f"Unsupported time_in_force: {time_in_force}"
        ) from exc


def _parse_order_status(
    status: str,
) -> QueryOrderStatus:
    try:
        return QueryOrderStatus(
            status.strip().lower()
        )

    except ValueError as exc:
        raise ValueError(
            "status must normally be "
            "'open', 'closed' or 'all'."
        ) from exc


@tool
def place_market_order(
    symbol: str,
    side: str,
    qty: float | None = None,
    notional: float | None = None,
    client_order_id: str | None = None,
) -> dict:
    """
    Submit a market order.

    Exactly one of qty or notional must be provided.

    Examples:
        Buy 5 shares:
            symbol="AAPL", side="buy", qty=5

        Invest $2000:
            symbol="NVDA", side="buy", notional=2000
    """

    if (qty is None) == (notional is None):
        raise ValueError(
            "Specify exactly one of qty or notional."
        )

    if qty is not None and qty <= 0:
        raise ValueError(
            "qty must be greater than 0."
        )

    if notional is not None and notional <= 0:
        raise ValueError(
            "notional must be greater than 0."
        )

    try:
        client = get_trading_client()

        request = MarketOrderRequest(
            symbol=normalize_symbol(symbol),
            side=_parse_side(side),
            qty=qty,
            notional=notional,
            time_in_force=TimeInForce.DAY,
            client_order_id=client_order_id,
        )

        order = client.submit_order(
            order_data=request,
        )

        return success(
            order=order,
        )

    except APIError as exc:
        return api_error(exc)


@tool
def place_limit_order(
    symbol: str,
    side: str,
    qty: float,
    limit_price: float,
    time_in_force: str = "day",
    extended_hours: bool = False,
    client_order_id: str | None = None,
) -> dict:
    """
    Submit a limit order.

    The order will only execute at the limit price or better.
    """

    if qty <= 0:
        raise ValueError(
            "qty must be greater than 0."
        )

    if limit_price <= 0:
        raise ValueError(
            "limit_price must be greater than 0."
        )

    try:
        client = get_trading_client()

        request = LimitOrderRequest(
            symbol=normalize_symbol(symbol),
            qty=qty,
            side=_parse_side(side),
            limit_price=limit_price,
            time_in_force=_parse_time_in_force(
                time_in_force
            ),
            extended_hours=extended_hours,
            client_order_id=client_order_id,
        )

        order = client.submit_order(
            order_data=request,
        )

        return success(
            order=order,
        )

    except APIError as exc:
        return api_error(exc)


@tool
def place_stop_order(
    symbol: str,
    side: str,
    qty: float,
    stop_price: float,
    time_in_force: str = "day",
    client_order_id: str | None = None,
) -> dict:
    """
    Submit a stop order.

    When the stop price is reached, the order becomes
    a market order.
    """

    if qty <= 0:
        raise ValueError(
            "qty must be greater than 0."
        )

    if stop_price <= 0:
        raise ValueError(
            "stop_price must be greater than 0."
        )

    try:
        client = get_trading_client()

        request = StopOrderRequest(
            symbol=normalize_symbol(symbol),
            qty=qty,
            side=_parse_side(side),
            stop_price=stop_price,
            time_in_force=_parse_time_in_force(
                time_in_force
            ),
            client_order_id=client_order_id,
        )

        order = client.submit_order(
            order_data=request,
        )

        return success(
            order=order,
        )

    except APIError as exc:
        return api_error(exc)


@tool
def place_stop_limit_order(
    symbol: str,
    side: str,
    qty: float,
    stop_price: float,
    limit_price: float,
    time_in_force: str = "day",
    client_order_id: str | None = None,
) -> dict:
    """
    Submit a stop-limit order.

    The stop price activates the order, then the limit price
    controls the worst acceptable execution price.
    """

    if qty <= 0:
        raise ValueError(
            "qty must be greater than 0."
        )

    if stop_price <= 0:
        raise ValueError(
            "stop_price must be greater than 0."
        )

    if limit_price <= 0:
        raise ValueError(
            "limit_price must be greater than 0."
        )

    try:
        client = get_trading_client()

        request = StopLimitOrderRequest(
            symbol=normalize_symbol(symbol),
            qty=qty,
            side=_parse_side(side),
            stop_price=stop_price,
            limit_price=limit_price,
            time_in_force=_parse_time_in_force(
                time_in_force
            ),
            client_order_id=client_order_id,
        )

        order = client.submit_order(
            order_data=request,
        )

        return success(
            order=order,
        )

    except APIError as exc:
        return api_error(exc)


@tool
def place_trailing_stop_order(
    symbol: str,
    side: str,
    qty: float,
    trail_percent: float | None = None,
    trail_price: float | None = None,
    time_in_force: str = "gtc",
    client_order_id: str | None = None,
) -> dict:
    """
    Submit a trailing stop order.

    Provide exactly one of:
        trail_percent
        trail_price
    """

    if qty <= 0:
        raise ValueError(
            "qty must be greater than 0."
        )

    if (
        trail_percent is None
        and trail_price is None
    ):
        raise ValueError(
            "Specify trail_percent or trail_price."
        )

    if (
        trail_percent is not None
        and trail_price is not None
    ):
        raise ValueError(
            "Specify only one of trail_percent "
            "or trail_price."
        )

    if (
        trail_percent is not None
        and trail_percent <= 0
    ):
        raise ValueError(
            "trail_percent must be greater than 0."
        )

    if (
        trail_price is not None
        and trail_price <= 0
    ):
        raise ValueError(
            "trail_price must be greater than 0."
        )

    try:
        client = get_trading_client()

        request = TrailingStopOrderRequest(
            symbol=normalize_symbol(symbol),
            qty=qty,
            side=_parse_side(side),
            trail_percent=trail_percent,
            trail_price=trail_price,
            time_in_force=_parse_time_in_force(
                time_in_force
            ),
            client_order_id=client_order_id,
        )

        order = client.submit_order(
            order_data=request,
        )

        return success(
            order=order,
        )

    except APIError as exc:
        return api_error(exc)


@tool
def place_bracket_market_order(
    symbol: str,
    side: str,
    qty: float,
    take_profit_price: float,
    stop_loss_price: float,
    stop_loss_limit_price: float | None = None,
    client_order_id: str | None = None,
) -> dict:
    """
    Submit a market order with attached take-profit and stop-loss.

    This is useful when a position should automatically have
    predefined risk management.

    Example:
        Buy AAPL with:
        take_profit_price=280
        stop_loss_price=240
    """

    if qty <= 0:
        raise ValueError(
            "qty must be greater than 0."
        )

    if take_profit_price <= 0:
        raise ValueError(
            "take_profit_price must be greater than 0."
        )

    if stop_loss_price <= 0:
        raise ValueError(
            "stop_loss_price must be greater than 0."
        )

    try:
        client = get_trading_client()

        stop_loss = StopLossRequest(
            stop_price=stop_loss_price,
            limit_price=stop_loss_limit_price,
        )

        take_profit = TakeProfitRequest(
            limit_price=take_profit_price,
        )

        request = MarketOrderRequest(
            symbol=normalize_symbol(symbol),
            qty=qty,
            side=_parse_side(side),
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            take_profit=take_profit,
            stop_loss=stop_loss,
            client_order_id=client_order_id,
        )

        order = client.submit_order(
            order_data=request,
        )

        return success(
            order=order,
        )

    except APIError as exc:
        return api_error(exc)


@tool
def get_orders(
    status: str = "open",
    symbols: list[str] | None = None,
    limit: int = 50,
) -> dict:
    """
    Retrieve orders from Alpaca.

    status should normally be:
        "open"
        "closed"
        "all"
    """

    if limit <= 0 or limit > 500:
        raise ValueError(
            "limit must be between 1 and 500."
        )

    if symbols:
        symbols = [
            normalize_symbol(symbol)
            for symbol in symbols
        ]

    try:
        client = get_trading_client()

        request = GetOrdersRequest(
            status=_parse_order_status(status),
            symbols=symbols,
            limit=limit,
            nested=True,
        )

        orders = client.get_orders(
            filter=request,
        )

        return success(
            orders=orders,
            order_count=len(orders),
        )

    except APIError as exc:
        return api_error(exc)


@tool
def get_order_by_id(
    order_id: str,
) -> dict:
    """
    Retrieve a single Alpaca order using its order ID.
    """

    try:
        client = get_trading_client()

        order = client.get_order_by_id(
            order_id
        )

        return success(
            order=order,
        )

    except APIError as exc:
        return api_error(exc)


@tool
def replace_order(
    order_id: str,
    qty: int | None = None,
    limit_price: float | None = None,
    stop_price: float | None = None,
) -> dict:
    """
    Modify an existing open order.

    Only supply the fields that should change.
    """

    if (
        qty is None
        and limit_price is None
        and stop_price is None
    ):
        raise ValueError(
            "At least one replacement value "
            "must be provided."
        )

    try:
        client = get_trading_client()

        request = ReplaceOrderRequest(
            qty=qty,
            limit_price=limit_price,
            stop_price=stop_price,
        )

        order = client.replace_order_by_id(
            order_id=order_id,
            order_data=request,
        )

        return success(
            order=order,
        )

    except APIError as exc:
        return api_error(exc)


@tool
def cancel_order(
    order_id: str,
) -> dict:
    """
    Cancel one open order by order ID.
    """

    try:
        client = get_trading_client()

        client.cancel_order_by_id(
            order_id
        )

        return success(
            cancelled=True,
            order_id=order_id,
        )

    except APIError as exc:
        return api_error(exc)


@tool
def cancel_all_orders() -> dict:
    """
    EMERGENCY TOOL.

    Attempt to cancel every currently open order.
    """

    try:
        client = get_trading_client()

        results = client.cancel_orders()

        return success(
            results=results,
        )

    except APIError as exc:
        return api_error(exc)