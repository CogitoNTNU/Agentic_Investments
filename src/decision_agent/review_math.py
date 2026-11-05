"""Deterministic review arithmetic. No broker calls or order submission."""
from decimal import Decimal, ROUND_DOWN

from .trading import PRICE_BUFFER


def portfolio_facts(snapshot):
    context = snapshot["market_context"]
    cash = Decimal(snapshot["cash"])
    available = Decimal(snapshot["available_cash"])
    weights = sorted(context["holdings"].items(),
                     key=lambda item: Decimal(item[1]["weight_pct"]), reverse=True)
    return {
        "position_count": len([q for q in snapshot["positions"].values() if Decimal(q) > 0]),
        "cash_balance": str(cash),
        "available_cash_after_all_reservations": str(available),
        "cash_unavailable_for_new_buys": str(max(Decimal(0), cash - available)),
        "cash_rule": "available_cash already excludes open buy orders and local replacement reserves. "
                     "Do not subtract them again. Do not include prospective sale proceeds.",
        "largest_positions": [{"ticker": s, "weight_pct": d["weight_pct"]} for s, d in weights[:5]],
        "top_five_weight_pct": str(sum((Decimal(d["weight_pct"]) for _, d in weights[:5]), Decimal(0))),
        "risk_limits": "No user-approved maximum weights or loss budget supplied; do not invent one.",
        "correlations": "Not measured. Shared business drivers are qualitative exposures, not correlations.",
    }


def position_scenario(ticker, snapshot, action, quantity):
    """Pro forma mark-to-market exposure, conditional on a full fill at last trade."""
    if action not in {"buy", "sell", "hold"} or type(quantity) is not int or quantity < 0:
        raise ValueError("Invalid scenario action or whole-share quantity")
    if (action == "hold") != (quantity == 0):
        raise ValueError("Only HOLD has zero quantity")
    context = snapshot["market_context"]
    price = Decimal(context["prices"][ticker])
    equity = Decimal(context["estimated_equity"])
    current = Decimal(snapshot["positions"].get(ticker, "0"))
    after = current + (quantity if action == "buy" else -quantity if action == "sell" else 0)
    if after < 0:
        raise ValueError("Scenario would sell more than owned")
    if not price.is_finite() or price <= 0 or not equity.is_finite() or equity <= 0:
        raise ValueError("Invalid price or equity for scenario")
    weight_before = current * price / equity * 100
    weight_after = after * price / equity * 100
    # Same 2% buffered limit convention as execution, but execution rechecks quotes.
    limit = (price * PRICE_BUFFER).quantize(
        Decimal("0.01") if price * PRICE_BUFFER >= 1 else Decimal("0.0001"), rounding=ROUND_DOWN)
    budget = limit * quantity if action == "buy" else Decimal(0)
    spendable = max(Decimal(0), min(Decimal(snapshot["available_cash"]), Decimal(snapshot["buying_power"])))
    return {
        "ticker": ticker, "action": action, "shares_to_trade": quantity,
        "current_shares": str(current), "projected_shares_after_full_fill": str(after),
        "weight_before_pct": str(weight_before), "weight_after_pct": str(weight_after),
        "trade_notional_at_last_price": str(price * quantity),
        "buffered_buy_cost": str(budget), "cash_fundable_now": budget <= spendable,
        "cash_shortfall": str(max(Decimal(0), budget - spendable)),
        "available_cash_after_buy_reservation": str(Decimal(snapshot["available_cash"]) - budget),
        "stress_loss_pct_of_current_equity": {
            str(drop): {"before": str(weight_before * Decimal(drop) / 100),
                        "after": str(weight_after * Decimal(drop) / 100)} for drop in (20, 40, 60)
        },
        "assumptions": "Illustrative single-stock declines, not forecasts or calibrated probabilities. "
                       "Other prices unchanged; trade at last price; fees/slippage excluded, not assumed zero "
                       "for a real trade. Pending shares are not owned. Sale proceeds are not available yet.",
    }


def sizing_examples(ticker, snapshot):
    current = int(Decimal(snapshot["positions"].get(ticker, "0")))
    uncommitted = Decimal(current)
    for order in snapshot["open_orders"]:
        if order["symbol"] == ticker and order["side"] == "sell":
            if order.get("qty") is None:
                uncommitted = Decimal(0)
                break
            uncommitted -= Decimal(order["qty"]) - Decimal(order["filled_qty"])
    available = max(0, int(uncommitted))
    sells = sorted({min(available, max(1, current // 4)),
                    min(available, max(1, current // 2)), available}) if available else []
    return [position_scenario(ticker, snapshot, "hold", 0),
            *[position_scenario(ticker, snapshot, "buy", n) for n in (1, 2, 5, 10)],
            *[position_scenario(ticker, snapshot, "sell", n) for n in sells]]
