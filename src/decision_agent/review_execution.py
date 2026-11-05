"""Execute and reconcile review orders, retaining funding and broker receipts."""
import json
from decimal import Decimal
from uuid import uuid4

from . import trading
from .review import ReviewDecision, sellable_shares, compare_candidate, market_context, choice_math
from .review_math import portfolio_facts
from .schemas import Decision

FAILURE_STATES = {"failed", "incomplete_order", "incomplete_replacement", "needs_review", "stopped"}


def report_status(report):
    states = {e.get("execution", {}).get("state") for e in report.get("candidates", {}).values()}
    if "active" in states:
        return "awaiting_orders"
    if states & FAILURE_STATES:
        return "needs_attention"
    return "complete"


def migrate_execution_records(report):
    """Recover old reports that used 'complete' to mean merely submitted."""
    for entry in report.get("candidates", {}).values():
        execution = entry.get("execution", {})
        records = execution.get("orders", {})
        if (execution.get("state") == "failed" and not records
                and execution.get("reason") == "Estimated sale proceeds and free cash cannot fund the replacement"
                and "funding_reassessments" not in execution):
            # Old preflight failures are safe to send through a fresh full review.
            execution["state"] = "needs_review"
        if execution.get("state") == "complete":
            if any(o.get("status") in {"skipped_cash"} for o in records.values()):
                execution["state"] = "incomplete_replacement" if entry.get("rotation") else "failed"
            elif any(o.get("client_order_id") and o.get("status") not in trading.TERMINAL_STATUSES
                     for o in records.values()):
                execution["state"] = "active"


def reserved_cash(report, ticker, snapshot):
    """Exclude the owner's budget and avoid counting broker-held funds twice."""
    open_ids = {o["id"] for o in snapshot["open_orders"]}
    reserved = Decimal(0)
    for symbol, entry in report.get("candidates", {}).items():
        execution = entry.get("execution", {})
        if symbol == ticker or execution.get("state") != "active":
            continue
        buy = execution.get("orders", {}).get("buy", {})
        if buy.get("status") == "filled" or buy.get("order_id") in open_ids:
            continue
        budget = execution.get("reserved_cash")
        if budget is None and entry.get("rotation") and "risk_decision" in entry:
            # Older active rotations get a conservative reserve before new spending.
            budget = trading.buy_limit_price(symbol) * entry["rotation"]["buy_shares"]
        reserved += Decimal(str(budget or 0))
    return reserved


def budget_snapshot(report, ticker, snapshot):
    reserve = reserved_cash(report, ticker, snapshot)
    return {**snapshot, "replacement_reserved_cash": str(reserve),
            "available_cash": str(max(Decimal(0), Decimal(snapshot["available_cash"]) - reserve))}


def execute_recommendation(source, output, ticker, save_json, load_candidates, complete_candidate):
    report = json.loads(output.read_text(encoding="utf-8"))
    if report.get("queue_source") != str(source):
        raise ValueError("Generate a review for this queue first")
    migrate_execution_records(report)
    execute_entry(report, source, output, ticker, save_json, load_candidates, complete_candidate)
    report["status"] = report_status(report)
    save_json(output, report)


def _end_attempt(entry, reason):
    execution = entry["execution"]
    records = execution["orders"]
    filled = any(Decimal(o.get("filled_qty", "0")) > 0 for o in records.values())
    execution["state"] = ("incomplete_replacement" if filled and entry.get("rotation")
                          else "incomplete_order" if filled else "failed")
    execution["reason"] = reason
    execution["reserved_cash"] = "0"


def _validate_snapshot(entry, leg, fresh, choice):
    expected = dict(entry["snapshot"]["positions"])
    if leg.action == "buy" and choice.rotation:
        rotation = choice.rotation
        remaining = Decimal(expected[rotation.sell_ticker]) - rotation.sell_shares
        if remaining:
            expected[rotation.sell_ticker] = str(remaining)
        else:
            expected.pop(rotation.sell_ticker)
        symbols = {rotation.sell_ticker, leg.ticker}
    else:
        symbols = (set(expected) | set(fresh["positions"])
                   | {o["symbol"] for o in entry["snapshot"]["open_orders"]}
                   | {o["symbol"] for o in fresh["open_orders"]})
    positions = {s: q for s, q in fresh["positions"].items() if s in symbols}
    expected = {s: q for s, q in expected.items() if s in symbols}
    old_orders = [o for o in entry["snapshot"]["open_orders"] if o["symbol"] in symbols]
    new_orders = [o for o in fresh["open_orders"] if o["symbol"] in symbols]
    if expected != positions or old_orders != new_orders:
        raise trading.AccountChanged("Positions or open orders changed; a fresh review is required")
    if leg.action == "sell" and leg.number_of_stocks > sellable_shares(leg.ticker, fresh):
        raise trading.AccountChanged("Insufficient uncommitted shares")


def _reassess_funding(report, ticker, fresh, limit, available, proceeds, budget, save):
    """Reconsider an unfunded switch only before any order intent is recorded."""
    entry = report["candidates"][ticker]
    execution = entry["execution"]
    attempts = execution.setdefault("funding_reassessments", [])
    if (execution["orders"] or len(attempts) >= 2
            or not all(key in entry for key in ("assessment", "debate", "risk_decision"))):
        return False
    risk = entry["risk_decision"]
    if risk.get("action") != "buy" or not risk.get("number_of_stocks"):
        return False
    feedback = {"previous_choice": ReviewDecision.model_validate(entry).model_dump(),
                "buy_limit_price": str(limit), "free_cash": str(available),
                "estimated_sale_proceeds": str(proceeds), "required_cash": str(budget),
                "shortfall": str(budget - available - proceeds)}
    attempts.append(feedback)
    save()  # Bound retries across interruptions as well as within this process.
    snapshot = {**fresh, "available_cash": str(available), "market_context": market_context(ticker, fresh)}
    capacity = max(0, min(50, int(available // limit)))
    print(f"[{ticker}] Replacement underfunded; reassessing funding ({len(attempts)}/2).", flush=True)
    choice = compare_candidate(ticker, {**entry["assessment"], "debate": entry["debate"],
                               "decision": risk, "max_cash_buy_shares": capacity,
                               "funding_reassessment": feedback}, report["holdings"], snapshot)
    if choice.action == "buy_with_cash":
        choice.cash_buy_shares = min(choice.cash_buy_shares, capacity, risk["number_of_stocks"])
        if not choice.cash_buy_shares:
            choice = ReviewDecision(action="pass", rationale="No affordable cash purchase after reassessment.", rotation=None)
    elif choice.rotation:
        choice.rotation.buy_shares = min(choice.rotation.buy_shares, risk["number_of_stocks"])
    entry.update(choice.model_dump(), snapshot=snapshot,
                 portfolio_facts=portfolio_facts(snapshot),
                 planned_trade_math=choice_math(ticker, choice, snapshot))
    feedback["revised_choice"] = choice.model_dump()
    save()
    return True


def execute_entry(report, source, output, ticker, save_json, load_candidates, complete_candidate):
    entry = report["candidates"][ticker]
    choice = ReviewDecision.model_validate(entry)
    execution = entry.get("execution", {})
    if execution.get("state") in FAILURE_STATES | {"complete"}:
        return
    if not execution and ticker not in {c["ticker"] for c in load_candidates(source)}:
        raise ValueError(f"{ticker} is no longer queued")
    legs = []
    if choice.rotation:
        r = choice.rotation
        if choice.action != "propose_replacement" or r.sell_ticker == ticker or r.buy_ticker != ticker:
            raise ValueError("Invalid replacement")
        legs.append(Decision(ticker=r.sell_ticker, action="sell", number_of_stocks=r.sell_shares))
        legs.append(Decision(ticker=ticker, action="buy", number_of_stocks=r.buy_shares))
    elif choice.action == "sell":
        legs.append(Decision(ticker=ticker, action="sell", number_of_stocks=choice.sell_shares))
    elif choice.action == "buy_with_cash":
        legs.append(Decision(ticker=ticker, action="buy", number_of_stocks=choice.cash_buy_shares))
    if not execution:
        execution = entry["execution"] = {"state": "active", "orders": {}}

    for leg in legs:
        records = execution["orders"]
        record = records.get(leg.action)
        order = None
        if record:
            try:
                order = trading.get_client().get_order_by_client_id(record["client_order_id"])
            except Exception as error:
                if getattr(error, "status_code", None) != 404 or "status" in record:
                    raise
        if order is None:
            if "risk_decision" not in entry:
                execution.update(state="needs_review", reserved_cash="0",
                                 reason="Fresh bull/bear debate required before submission")
                save_json(output, report)
                return
            fresh = trading.account_snapshot(leg.ticker)
            reserve = reserved_cash(report, ticker, fresh)
            try:
                _validate_snapshot(entry, leg, fresh, choice)
                if choice.rotation and "buy_limit" not in execution:
                    limit = trading.buy_limit_price(ticker)
                    budget = limit * choice.rotation.buy_shares
                    available = max(Decimal(0), min(Decimal(fresh["available_cash"]),
                                                   Decimal(fresh["buying_power"])) - reserve)
                    # Plan with a 2% haircut on the sale; actual proceeds are rechecked.
                    sale_price = trading.get_latest_prices([leg.ticker])[leg.ticker]
                    proceeds = sale_price * choice.rotation.sell_shares * Decimal("0.98")
                    if available + proceeds < budget:
                        if _reassess_funding(report, ticker, fresh, limit, available, proceeds, budget,
                                             lambda: save_json(output, report)):
                            return execute_entry(report, source, output, ticker, save_json,
                                                 load_candidates, complete_candidate)
                        raise trading.InsufficientCash("Estimated sale proceeds and free cash cannot fund the replacement")
                    execution.update(buy_limit=str(limit), reserved_cash=str(budget))
                if leg.action == "buy" and "buy_limit" not in execution:
                    limit = trading.buy_limit_price(ticker)
                    execution.update(buy_limit=str(limit), reserved_cash=str(limit * leg.number_of_stocks))
                limit = Decimal(execution["buy_limit"]) if execution.get("buy_limit") else None
                if record is None:
                    record = records[leg.action] = {"client_order_id": f"review-{uuid4().hex}"}
                save_json(output, report)
                order = trading.execute_decision(
                    leg, expected_number_of_stocks=fresh["current_number_of_stocks"],
                    expected_account=fresh, portfolio_source="alpaca",
                    client_order_id=record["client_order_id"], reserved_cash=reserve,
                    buy_limit=limit if leg.action == "buy" else None, review_order=True,
                )
            except (trading.AccountChanged, trading.OrderRejected) as error:
                _end_attempt(entry, str(error))
                save_json(output, report)
                print(f"[{ticker}] {execution['state']}: {error}. Continuing queue.", flush=True)
                return
        trading._validate_order({"decision": leg.model_dump(), **record}, order)
        status = getattr(order.status, "value", order.status)
        observed = dict(status=status, filled_qty=str(order.filled_qty or 0), order_id=str(order.id))
        if any(record.get(k) != v for k, v in observed.items()):
            record.update(observed)
            save_json(output, report)
            print(f"[{leg.ticker}] {leg.action} {leg.number_of_stocks}: {status}, filled {record['filled_qty']}")
        # Resolve the shared submission journal after an interrupted API response.
        path = trading._pending_path()
        if path.exists():
            pending = json.loads(path.read_text(encoding="utf-8"))
            if pending["client_order_id"] == record["client_order_id"]:
                path.unlink()
        if status in {"rejected", "expired", "canceled"}:
            _end_attempt(entry, f"{leg.action} order ended as {status}")
            save_json(output, report)
            return
        if status == "filled" and Decimal(record["filled_qty"]) != leg.number_of_stocks:
            raise RuntimeError("Broker filled status disagrees with filled quantity")
        if status != "filled":
            return
    complete_candidate(ticker, source)
    execution.update(state="complete", reserved_cash="0")
    save_json(output, report)
