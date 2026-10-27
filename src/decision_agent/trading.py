"""Submit paper orders and reconcile confirmed fills with the local portfolio."""

import json
from decimal import Decimal
from time import monotonic, sleep
from uuid import uuid4

from . import portfolio
from .schemas import Decision

TERMINAL_STATUSES = {"filled", "canceled", "expired", "rejected"}


def get_client():
    # Keep Alpaca optional for research-only imports and hold decisions.
    from ..alpaca_tools.client import get_trading_client

    return get_trading_client()


def _pending_path():
    return portfolio.PORTFOLIO_PATH.with_suffix(".pending.json")


def _reconcile(pending: dict, order) -> bool:
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
    delta = int(filled) * (1 if decision.action == "buy" else -1)
    portfolio.set_holding(decision.ticker, pending["previous_holding"] + delta)
    status = getattr(order.status, "value", order.status)
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
        client = get_client()
        order = client.get_order_by_client_id(pending["client_order_id"])
        if not _reconcile(pending, order):
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
    """Validate locally, submit once, then persist only confirmed fills."""
    decision = Decision.model_validate(decision)
    with portfolio._lock:
        sync_pending_order()
        current = portfolio.get_number_of_stocks(decision.ticker)
        if current != expected_number_of_stocks:
            raise ValueError("Holding changed during decision; run the analysis again")
        if decision.action == "hold":
            return
        if decision.action == "sell" and decision.number_of_stocks > current:
            raise ValueError("Cannot sell more stocks than the portfolio holds")

        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        client = get_client()
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
        client_order_id = f"decision-{uuid4().hex}"
        request = MarketOrderRequest(
            symbol=decision.ticker,
            qty=decision.number_of_stocks,
            side=OrderSide(decision.action),
            time_in_force=TimeInForce.DAY,
            client_order_id=client_order_id,
        )
        pending = {
            "client_order_id": client_order_id,
            "decision": decision.model_dump(),
            "previous_holding": current,
        }
        # Save before submission: even an ambiguous network failure can be recovered
        # by client_order_id instead of risking a second trade.
        path = _pending_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as saved:
            json.dump(pending, saved, indent=2)
        try:
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
