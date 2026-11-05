"""Submit paper orders, booking received orders immediately when the market is closed."""

import json
from decimal import Decimal, ROUND_DOWN
from time import monotonic, sleep
from uuid import uuid4

from . import portfolio
from .schemas import Decision

TERMINAL_STATUSES = {"filled", "canceled", "expired", "rejected"}
# Cap the buy execution price so a price jump cannot exceed the checked cash budget.
PRICE_BUFFER = Decimal("1.02")


def get_client():
    # Keep Alpaca optional for research-only imports and hold decisions.
    from ..alpaca_tools.client import get_trading_client

    return get_trading_client()


def get_latest_prices(symbols: list[str]) -> dict[str, Decimal]:
    from alpaca.data.requests import StockLatestTradeRequest

    from ..alpaca_tools.client import get_data_client

    trades = get_data_client().get_stock_latest_trade(
        StockLatestTradeRequest(symbol_or_symbols=symbols)
    )
    return {symbol: Decimal(str(trade.price)) for symbol, trade in trades.items()}


def _check_cash(client, decision: Decision) -> Decimal:
    """Return a cash-backed limit, reserving maximum remaining open-buy commitments."""
    from alpaca.trading.enums import OrderSide, QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    open_buys = client.get_orders(
        filter=GetOrdersRequest(status=QueryOrderStatus.OPEN, side=OrderSide.BUY, limit=500)
    )
    if len(open_buys) >= 500:
        raise ValueError("Cannot verify the complete list of open buy orders")
    price = get_latest_prices([decision.ticker])[decision.ticker]
    if not price.is_finite() or price <= 0:
        raise ValueError("Invalid latest trade price")
    buffered = price * PRICE_BUFFER
    limit = buffered.quantize(Decimal("0.01") if buffered >= 1 else Decimal("0.0001"), rounding=ROUND_DOWN)
    if limit <= 0:
        raise ValueError("Invalid buy limit price")
    cash = Decimal(str(client.get_account().cash))
    if not cash.is_finite():
        raise ValueError("Invalid Alpaca cash balance")
    reserved = Decimal(0)
    for order in open_buys:
        if order.notional is not None:
            # Conservatively reserve full notional until the order closes.
            commitment = Decimal(str(order.notional))
            if not commitment.is_finite() or commitment < 0:
                raise ValueError("Invalid open-order notional")
            reserved += commitment
        else:
            quantity = Decimal(str(order.qty))
            filled = Decimal(str(order.filled_qty or 0))
            if (not quantity.is_finite() or not filled.is_finite()
                    or quantity < 0 or filled < 0 or filled > quantity):
                raise ValueError("Invalid open-order quantities")
            remaining = quantity - filled
            if not remaining:
                continue
            if order.limit_price is None:
                # An unfilled share-based market order has no bounded cost.
                raise ValueError("Cannot verify available cash while an unpriced buy order is open")
            order_limit = Decimal(str(order.limit_price))
            if not order_limit.is_finite() or order_limit <= 0:
                raise ValueError("Invalid open-order limit price")
            reserved += remaining * order_limit
    available = max(Decimal(0), cash - reserved)
    cost = decision.number_of_stocks * limit
    if cost > available:
        raise ValueError(
            f"Not enough cash to buy {decision.number_of_stocks} {decision.ticker}: "
            f"needs ${cost:.2f}, ${available:.2f} available "
            "after open buy orders"
        )
    return limit


def _pending_path():
    return portfolio.PORTFOLIO_PATH.with_suffix(".pending.json")


def _validate_order(pending: dict, order) -> Decision:
    decision = Decision.model_validate(pending["decision"])
    if (
        order.symbol != decision.ticker
        or order.side != decision.action
        or order.client_order_id != pending["client_order_id"]
    ):
        raise RuntimeError("Alpaca order does not match the saved decision")
    filled = Decimal(str(order.filled_qty or 0))
    if (
        not filled.is_finite()
        or filled < 0
        or filled > decision.number_of_stocks
        or filled != int(filled)
    ):
        raise RuntimeError("Unexpected Alpaca filled quantity; pending order retained")
    return decision


def _book_received_order(pending: dict, order) -> None:
    """Record the entire received order as a normal portfolio holding."""
    decision = _validate_order(pending, order)
    delta = decision.number_of_stocks * (1 if decision.action == "buy" else -1)
    updated = pending["previous_holding"] + delta
    # Absolute quantity also makes recovery safe if the write succeeded before a crash.
    portfolio.set_holding(decision.ticker, updated)
    _pending_path().unlink()
    print(
        f"[{decision.ticker}] Ordre mottatt utenfor åpningstid. "
        f"Registrert {decision.action.upper()} {decision.number_of_stocks} aksjer. "
        f"Beholdning: {updated}. Fortsetter køen.",
        flush=True,
    )


def _finish_received_order(pending: dict, order) -> bool:
    status = getattr(order.status, "value", order.status)
    if pending.get("book_on_acceptance") and status not in TERMINAL_STATUSES:
        _book_received_order(pending, order)
        return True
    return _reconcile(pending, order)


def _reconcile(pending: dict, order) -> bool:
    decision = _validate_order(pending, order)
    filled = Decimal(str(order.filled_qty or 0))
    delta = int(filled) * (1 if decision.action == "buy" else -1)
    updated = pending["previous_holding"] + delta
    previous = portfolio.get_number_of_stocks(decision.ticker)
    portfolio.set_holding(decision.ticker, updated)
    status = getattr(order.status, "value", order.status)
    if updated != previous or status in TERMINAL_STATUSES:
        action = "kjøpt" if decision.action == "buy" else "solgt"
        print(
            f"[{decision.ticker}] Alpaca: {status}. Bekreftet {action}: "
            f"{filled}/{decision.number_of_stocks} aksjer. Beholdning: {updated}",
            flush=True,
        )
    if status in TERMINAL_STATUSES:
        _pending_path().unlink()
        if status != "filled":
            raise RuntimeError(
                f"Alpaca order {order.id} ended as {status}; "
                f"only {filled} executed shares were recorded"
            )
        return True
    return False


def sync_pending_order() -> None:
    """Recover a pending order without ever submitting it again."""
    with portfolio._lock:
        if not _pending_path().exists():
            return
        pending = json.loads(_pending_path().read_text(encoding="utf-8"))
        print(f"[Alpaca] Avklarer tidligere ordre {pending['client_order_id']}", flush=True)
        client = get_client()
        order = client.get_order_by_client_id(pending["client_order_id"])
        # Also recover orders saved by the old version during a closed session.
        if "book_on_acceptance" not in pending:
            pending["book_on_acceptance"] = not client.get_clock().is_open
        if not _finish_received_order(pending, order):
            raise RuntimeError(
                f"Alpaca order {order.id} is still pending; confirmed fills were synced. "
                "Call sync_pending_order() again later; no new order was submitted."
            )


def execute_decision(
    decision: Decision,
    expected_number_of_stocks: int,
    timeout: float = 30,
    poll_interval: float = 1,
) -> None:
    """Book received orders immediately outside hours; await fills during trading."""
    decision = Decision.model_validate(decision)
    with portfolio._lock:
        sync_pending_order()
        current = portfolio.get_number_of_stocks(decision.ticker)
        if current != expected_number_of_stocks:
            raise ValueError("Holding changed during decision; run the analysis again")
        if decision.action == "hold":
            print(f"[{decision.ticker}] HOLD: ingen ordre sendt. Beholdning: {current} aksjer", flush=True)
            return
        if decision.action == "buy" and decision.number_of_stocks > 50:
            raise ValueError("Cannot buy more than 50 stocks per decision")
        if decision.action == "sell" and decision.number_of_stocks > current:
            raise ValueError("Cannot sell more stocks than the portfolio holds")

        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest

        client = get_client()
        book_on_acceptance = not client.get_clock().is_open
        if not book_on_acceptance:
            print(f"[{decision.ticker}] Kontrollerer beholdning hos Alpaca", flush=True)
            broker_quantity = next(
                (
                    Decimal(str(p.qty))
                    for p in client.get_all_positions()
                    if p.symbol == decision.ticker
                ),
                Decimal(0),
            )
            if broker_quantity != current:
                raise ValueError(
                    "Alpaca holding differs from portfolio.json; reconcile it before trading"
                )
        buy_limit = _check_cash(client, decision) if decision.action == "buy" else None
        client_order_id = f"decision-{uuid4().hex}"
        request_type = LimitOrderRequest if decision.action == "buy" else MarketOrderRequest
        request = request_type(
            symbol=decision.ticker,
            qty=decision.number_of_stocks,
            side=OrderSide(decision.action),
            time_in_force=TimeInForce.DAY,
            client_order_id=client_order_id,
            **({"limit_price": float(buy_limit)} if buy_limit is not None else {}),
        )
        pending = {
            "client_order_id": client_order_id,
            "decision": decision.model_dump(),
            "previous_holding": current,
            "book_on_acceptance": book_on_acceptance,
        }
        # Save before submission: even an ambiguous network failure can be recovered
        # by client_order_id instead of risking a second trade.
        path = _pending_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as saved:
            json.dump(pending, saved, indent=2)
        try:
            print(
                f"[{decision.ticker}] Sender paperordre: {decision.action.upper()} "
                f"{decision.number_of_stocks} aksjer ({client_order_id})",
                flush=True,
            )
            order = client.submit_order(order_data=request)
        except Exception as error:
            # These HTTP responses definitively reject this submission. Network
            # errors and ambiguous server failures must retain the recovery record.
            if getattr(error, "status_code", None) in {400, 401, 403, 404, 422}:
                path.unlink()
                raise RuntimeError(
                    "Alpaca rejected the order; portfolio unchanged"
                ) from error
            raise RuntimeError(
                f"Alpaca submission failed or is uncertain ({client_order_id}). "
                "Pending record retained; check Alpaca before retrying."
            ) from error
        print(f"[{decision.ticker}] Ordre {order.id} mottatt", flush=True)
        if _finish_received_order(pending, order):
            return
        print(f"[{decision.ticker}] Venter på bekreftet utførelse", flush=True)
        deadline = monotonic() + timeout
        while True:
            if _reconcile(pending, order):
                return
            if monotonic() >= deadline:
                raise TimeoutError(
                    f"Alpaca order {order.id} is pending. Confirmed fills were synced; "
                    "call sync_pending_order() later. Do not resubmit the order."
                )
            sleep(poll_interval)
            order = client.get_order_by_id(order.id)
