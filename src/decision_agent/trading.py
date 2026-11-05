"""Submit paper orders, booking received orders immediately when the market is closed."""

import json
from decimal import Decimal, ROUND_DOWN
from time import monotonic, sleep
from uuid import uuid4

from . import portfolio
from .schemas import Decision

TERMINAL_STATUSES = {"filled", "canceled", "expired", "rejected"}
# Market orders can fill above the last trade price; keep headroom so buys stay off margin.
PRICE_BUFFER = Decimal("1.02")


def get_client():
    # Keep Alpaca optional for research-only imports and hold decisions.
    from ..alpaca_tools.client import get_trading_client

    return get_trading_client()


def get_holding(ticker: str, portfolio_source: str) -> int:
    if portfolio_source == "json":
        return portfolio.get_number_of_stocks(ticker)
    if portfolio_source != "alpaca":
        raise ValueError(f"Unknown portfolio source: {portfolio_source}")
    for position in get_client().get_all_positions():
        if position.symbol == ticker:
            quantity = Decimal(str(position.qty))
            if not quantity.is_finite() or quantity < 0 or quantity != quantity.to_integral_value():
                raise ValueError(f"Expected a long, whole-share Alpaca position for {ticker}: {quantity}")
            return int(quantity)
    return 0


class OrderRejected(RuntimeError):
    """The broker definitively declined the order."""


class AccountChanged(ValueError):
    """The final decision needs a fresh broker snapshot."""


def _quantity_text(value):
    return None if value is None else format(Decimal(str(value)).normalize(), "f")


def _cash_available(cash: Decimal, open_buys: list[dict]) -> Decimal:
    """Reserve the maximum outstanding purchase cost, including partial fills."""
    reserved = Decimal(0)
    for order in open_buys:
        if order["notional"] is not None:
            # Reserve the full notional conservatively until the order closes.
            reserved += Decimal(order["notional"])
        elif order["limit_price"] is not None:
            remaining = Decimal(order["qty"]) - Decimal(order["filled_qty"])
            reserved += remaining * Decimal(order["limit_price"])
        else:
            # An existing share-based market buy has no maximum execution price.
            return Decimal(0)
    return max(Decimal(0), cash - reserved)


def _buy_terms(order) -> dict:
    return {
        "qty": _quantity_text(order.qty), "filled_qty": _quantity_text(order.filled_qty),
        "notional": _quantity_text(order.notional), "limit_price": _quantity_text(order.limit_price),
    }


def account_snapshot(ticker: str) -> dict:
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    client = get_client()
    broker_positions = client.get_all_positions()
    positions = {p.symbol: _quantity_text(p.qty) for p in broker_positions}
    details = {}
    for position in broker_positions:
        value = getattr(position, "avg_entry_price", None)
        if isinstance(value, (str, int, float, Decimal)):
            average = Decimal(str(value))
            if average.is_finite() and average > 0:
                details[position.symbol] = {"avg_entry_price": str(average)}
    quantity = Decimal(positions.get(ticker, "0"))
    if not quantity.is_finite() or quantity < 0 or quantity != quantity.to_integral_value():
        raise ValueError(f"Expected a long, whole-share position for {ticker}: {quantity}")
    account = client.get_account()
    buying_power = Decimal(str(account.buying_power))
    cash = Decimal(str(account.cash))
    if not buying_power.is_finite() or not cash.is_finite():
        raise ValueError("Alpaca returned invalid account balances")
    orders = client.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=500))
    if len(orders) >= 500:
        raise ValueError("Cannot verify the complete list of open orders")
    open_orders = [
        {
            "id": str(o.id), "symbol": o.symbol, "side": o.side, "status": o.status,
            **_buy_terms(o),
        }
        for o in orders
    ]
    return {
        "positions": positions, "current_number_of_stocks": int(quantity),
        "buying_power": str(buying_power), "cash": str(cash),
        "available_cash": str(_cash_available(cash, [o for o in open_orders if o["side"] == "buy"])),
        "open_orders": sorted(open_orders, key=lambda o: o["id"]),
        "position_details": details,
    }


def get_latest_prices(symbols: list[str]) -> dict[str, Decimal]:
    from alpaca.data.requests import StockLatestTradeRequest

    from ..alpaca_tools.client import get_data_client

    trades = get_data_client().get_stock_latest_trade(
        StockLatestTradeRequest(symbol_or_symbols=symbols)
    )
    return {symbol: Decimal(str(trade.price)) for symbol, trade in trades.items()}


class InsufficientCash(AccountChanged):
    """A buy cannot fit the current cash budget."""


def buy_limit_price(ticker):
    price = get_latest_prices([ticker])[ticker] * PRICE_BUFFER
    tick = Decimal("0.01") if price >= 1 else Decimal("0.0001")
    limit = price.quantize(tick, rounding=ROUND_DOWN)
    if not limit.is_finite() or limit <= 0:
        raise ValueError(f"Invalid buy limit for {ticker}")
    return limit


def _cash_backed_limit(client, decision: Decision, snapshot: dict | None, *, limit: Decimal | None = None) -> Decimal:
    """Return the buy limit only if cash covers every share at that price."""
    from alpaca.trading.enums import OrderSide, QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    if snapshot is None:
        orders = client.get_orders(filter=GetOrdersRequest(
            status=QueryOrderStatus.OPEN, side=OrderSide.BUY, limit=500
        ))
        if len(orders) >= 500:
            raise ValueError("Cannot verify the complete list of open buy orders")
        available = _cash_available(Decimal(client.get_account().cash), [_buy_terms(o) for o in orders])
    else:
        available = min(Decimal(snapshot["available_cash"]), Decimal(snapshot["buying_power"]))

    limit = limit if limit is not None else buy_limit_price(decision.ticker)
    cost = decision.number_of_stocks * limit
    if cost > available:
        error = InsufficientCash if snapshot is not None else ValueError
        raise error(
            f"Not enough cash to buy {decision.number_of_stocks} {decision.ticker}: "
            f"needs ${cost:.2f}, ${available:.2f} available after open buy orders"
        )
    return limit


def _pending_path():
    return portfolio.PORTFOLIO_PATH.with_suffix(".pending.json")


def acknowledge_candidate(ticker, source) -> None:
    path = _pending_path()
    if path.exists():
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if receipt.get("queue_source") == str(source) and receipt["decision"]["ticker"] == ticker:
            path.unlink()


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
    if not pending.get("queue_source"):
        _pending_path().unlink()
    print(
        f"[{decision.ticker}] Ordre mottatt utenfor åpningstid. "
        f"Registrert {decision.action.upper()} {decision.number_of_stocks} aksjer. "
        f"Beholdning: {updated}. Fortsetter køen.",
        flush=True,
    )


def _finish_received_order(pending: dict, order) -> bool:
    status = getattr(order.status, "value", order.status)
    if pending.get("portfolio_source") == "alpaca":
        _validate_order(pending, order)
        if status in {"rejected", "expired", "canceled"} and not Decimal(str(order.filled_qty or 0)):
            _pending_path().unlink()
            raise OrderRejected(f"Alpaca order {order.id} ended as {status} without fills")
        # A queue-owned receipt survives until main has durably removed the candidate.
        if not pending.get("queue_source"):
            _pending_path().unlink()
        return True
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
        if not pending.get("queue_source") or status != "filled":
            _pending_path().unlink()
        if status != "filled":
            raise RuntimeError(
                f"Alpaca order {order.id} ended as {status}; "
                f"only {filled} executed shares were recorded"
            )
        return True
    return False


def sync_pending_order() -> dict | None:
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
        if pending.get("queue_source") and _pending_path().exists():
            return pending


def execute_decision(
    decision: Decision,
    expected_number_of_stocks: int,
    timeout: float = 30,
    poll_interval: float = 1,
    portfolio_source: str = "json",
    expected_account: dict | None = None,
    queue_source: str | None = None,
    client_order_id: str | None = None,
    reserved_cash: Decimal = Decimal(0),
    buy_limit: Decimal | None = None,
    review_order: bool = False,
):
    """Book received orders immediately outside hours; await fills during trading."""
    decision = Decision.model_validate(decision)
    with portfolio._lock:
        if sync_pending_order():
            raise RuntimeError("A handled candidate needs queue recovery before another order")
        if expected_account is not None:
            current = expected_account["current_number_of_stocks"]
        else:
            current = get_holding(decision.ticker, portfolio_source)
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
        from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

        client = get_client()
        book_on_acceptance = not client.get_clock().is_open
        if not book_on_acceptance and portfolio_source == "json":
            print(f"[{decision.ticker}] Kontrollerer beholdning hos Alpaca", flush=True)
            if get_holding(decision.ticker, "alpaca") != current:
                raise ValueError(
                    "Alpaca holding differs from portfolio.json; reconcile it before trading"
                )
        latest_account = None
        if expected_account is not None:
            latest_account = account_snapshot(decision.ticker)
            for field in ("positions", "open_orders"):
                if latest_account[field] != expected_account[field]:
                    raise AccountChanged(f"Alpaca {field} changed during the decision")
        client_order_id = client_order_id or f"decision-{uuid4().hex}"
        fields = dict(
            symbol=decision.ticker,
            qty=decision.number_of_stocks,
            side=OrderSide(decision.action),
            time_in_force=TimeInForce.DAY,
            client_order_id=client_order_id,
        )
        if decision.action == "buy":
            if latest_account is not None:
                latest_account["available_cash"] = str(max(
                    Decimal(0), Decimal(latest_account["available_cash"]) - reserved_cash
                ))
            limit = _cash_backed_limit(client, decision, latest_account, limit=buy_limit)
            request = LimitOrderRequest(**fields, limit_price=float(limit))
        else:
            request = MarketOrderRequest(**fields)
        pending = {
            "client_order_id": client_order_id,
            "decision": decision.model_dump(),
            "previous_holding": current,
            "queue_source": queue_source,
            "portfolio_source": portfolio_source,
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
                raise OrderRejected(
                    "Alpaca rejected the order; portfolio unchanged"
                ) from error
            raise RuntimeError(
                f"Alpaca submission failed or is uncertain ({client_order_id}). "
                "Pending record retained; check Alpaca before retrying."
            ) from error
        print(f"[{decision.ticker}] Ordre {order.id} mottatt", flush=True)
        if review_order:
            _validate_order(pending, order)
            path.unlink()
            return order
        if _finish_received_order(pending, order):
            return order
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
