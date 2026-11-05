import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src import main
from src.decision_agent import portfolio, trading, review_execution as execution


@pytest.fixture
def broker_run(monkeypatch, tmp_path):
    broker = MagicMock()
    monkeypatch.setattr(trading, "get_client", lambda: broker)
    monkeypatch.setattr(portfolio, "PORTFOLIO_PATH", tmp_path / "portfolio.json")
    positions = {"EIX": 5}
    balance = SimpleNamespace(cash="30", buying_power="30")
    orders = {}
    prices = {"EIX": Decimal("60"), "CCL": Decimal("29"), "COF": Decimal("100")}
    monkeypatch.setattr(trading, "get_latest_prices", lambda symbols: {s: prices[s] for s in symbols})
    broker.get_all_positions.side_effect = lambda: [SimpleNamespace(symbol=s, qty=str(q)) for s, q in positions.items() if q]
    broker.get_account.return_value = balance
    broker.get_clock.return_value = SimpleNamespace(is_open=True)
    broker.get_orders.side_effect = lambda **_: [o for o in orders.values() if o.status not in trading.TERMINAL_STATUSES]
    broker.get_order_by_client_id.side_effect = orders.__getitem__

    def submit(order_data):
        order = SimpleNamespace(id=order_data.client_order_id, client_order_id=order_data.client_order_id,
                                symbol=order_data.symbol, side=order_data.side, qty=str(int(order_data.qty)),
                                filled_qty="0", status="accepted", notional=None,
                                limit_price=str(order_data.limit_price) if order_data.side == "buy" else None)
        orders[order.client_order_id] = order
        return order
    broker.submit_order.side_effect = submit
    queue = tmp_path / "queue.json"
    queue.write_text('{"candidates":[{"ticker":"CCL"},{"ticker":"COF"}]}')
    output = tmp_path / "holdings_review.json"
    report = dict(mode="paper_queue", queue_source=str(queue), status="holdings_reviewed", candidates={})

    def add(ticker, rotation=False, quantity=1):
        report["candidates"][ticker] = dict(
            action="propose_replacement" if rotation else "buy_with_cash", rationale="test",
            risk_decision={"action": "buy"}, cash_buy_shares=0 if rotation else quantity,
            rotation=dict(sell_ticker="EIX", sell_shares=5, buy_ticker="CCL", buy_shares=quantity) if rotation else None,
            snapshot=trading.account_snapshot(ticker),
        )

    def run(ticker):
        execution.execute_entry(report, queue, output, ticker, main.save_json, main.load_candidates, main.complete_candidate)

    return SimpleNamespace(broker=broker, positions=positions, balance=balance, orders=orders,
                           prices=prices, report=report, queue=queue, output=output, add=add, run=run)


def test_rotation_reserves_proceeds_across_restart_and_prevents_other_buy(broker_run):
    r = broker_run
    r.add("CCL", rotation=True, quantity=10)
    r.run("CCL")
    sale = next(iter(r.orders.values()))
    assert sale.side == "sell"
    assert r.report["candidates"]["CCL"]["execution"]["reserved_cash"] == "295.80"
    # Sale fills while the queue researches another candidate.
    sale.status, sale.filled_qty = "filled", "5"
    r.positions["EIX"] = 0
    r.balance.cash = r.balance.buying_power = "330"
    r.report.update(json.loads(r.output.read_text()))
    snapshot = execution.budget_snapshot(r.report, "COF", trading.account_snapshot("COF"))
    assert Decimal(snapshot["available_cash"]) == Decimal("34.20")
    r.add("COF")
    r.run("COF")
    assert len(r.orders) == 1
    assert r.report["candidates"]["COF"]["execution"]["state"] == "failed"
    r.run("CCL")
    buy = next(o for o in r.orders.values() if o.side == "buy")
    assert Decimal(buy.limit_price) == Decimal("29.58")
    # Alpaca now reserves the order cost; the local reservation must not double count it.
    assert execution.reserved_cash(r.report, "COF", trading.account_snapshot("COF")) == 0
    buy.status, buy.filled_qty = "partially_filled", "4"
    r.run("CCL")
    assert r.report["candidates"]["CCL"]["execution"]["state"] == "active"
    assert "CCL" in {c["ticker"] for c in main.load_candidates(r.queue)}
    buy.status, buy.filled_qty = "filled", "10"
    r.run("CCL")
    r.run("CCL")
    assert r.broker.submit_order.call_count == 2
    assert r.report["candidates"]["CCL"]["execution"]["state"] == "complete"
    assert [c["ticker"] for c in main.load_candidates(r.queue)] == ["COF"]


def test_underfunded_rotation_does_not_sell(broker_run):
    r = broker_run
    r.add("CCL", rotation=True, quantity=20)
    r.run("CCL")
    r.broker.submit_order.assert_not_called()
    assert r.report["candidates"]["CCL"]["execution"]["state"] == "failed"
    assert "Estimated sale proceeds" in r.report["candidates"]["CCL"]["execution"]["reason"]


def prepare_funding_review(r):
    r.add("CCL", rotation=True, quantity=20)
    entry = r.report["candidates"]["CCL"]
    entry.update(assessment={"investment_case": "candidate"}, debate={"bear_analysis": "risks"},
                 risk_decision={"action": "buy", "number_of_stocks": 20})
    r.report["holdings"] = {"EIX": {"investment_case": "holding"}}
    return entry


def test_underfunded_rotation_reassessed_before_sale_and_resumes_once(broker_run, monkeypatch):
    r = broker_run
    entry = prepare_funding_review(r)

    def reconsider(ticker, assessment, holdings, snapshot):
        r.broker.submit_order.assert_not_called()
        assert assessment["debate"] == entry["debate"]
        feedback = assessment["funding_reassessment"]
        assert Decimal(feedback["shortfall"]) == Decimal("267.60")
        assert snapshot["available_cash"] == "30"
        return execution.ReviewDecision(action="propose_replacement", rationale="Smaller switch worthwhile",
            rotation=dict(sell_ticker="EIX", sell_shares=5, buy_ticker="CCL", buy_shares=10))

    choose = MagicMock(side_effect=reconsider)
    monkeypatch.setattr(execution, "compare_candidate", choose)
    r.run("CCL")
    r.report.update(json.loads(r.output.read_text()))
    r.run("CCL")
    choose.assert_called_once()
    assert r.broker.submit_order.call_count == 1
    sale = next(iter(r.orders.values()))
    sale.status, sale.filled_qty = "filled", "5"
    r.positions["EIX"] = 0
    r.balance.cash = r.balance.buying_power = "330"
    r.run("CCL")
    buy = next(o for o in r.orders.values() if o.side == "buy")
    assert buy.qty == "10"
    assert r.report["candidates"]["CCL"]["execution"]["reserved_cash"] == "295.80"


def test_funding_reassessment_can_pass_without_selling(broker_run, monkeypatch):
    r = broker_run
    prepare_funding_review(r)
    monkeypatch.setattr(execution, "compare_candidate", lambda *args: execution.ReviewDecision(
        action="pass", rationale="Smaller switch not worthwhile", rotation=None))
    r.run("CCL")
    r.broker.submit_order.assert_not_called()
    assert r.report["candidates"]["CCL"]["execution"]["state"] == "complete"


def test_unaffordable_reassessment_is_bounded_across_restart(broker_run, monkeypatch):
    r = broker_run
    entry = prepare_funding_review(r)
    choose = MagicMock(side_effect=lambda *args: execution.ReviewDecision.model_validate(entry))
    monkeypatch.setattr(execution, "compare_candidate", choose)
    r.run("CCL")
    r.report.update(json.loads(r.output.read_text()))
    execution.migrate_execution_records(r.report)
    r.run("CCL")
    assert choose.call_count == 2
    r.broker.submit_order.assert_not_called()
    assert r.report["candidates"]["CCL"]["execution"]["state"] == "failed"


def test_funding_reassessment_data_failure_never_sells(broker_run, monkeypatch):
    r = broker_run
    prepare_funding_review(r)
    monkeypatch.setattr(execution, "compare_candidate", MagicMock(side_effect=ConnectionError("offline")))
    with pytest.raises(ConnectionError):
        r.run("CCL")
    r.broker.submit_order.assert_not_called()
    assert "CCL" in {c["ticker"] for c in main.load_candidates(r.queue)}


def test_broker_changes_during_reassessment_block_sale(broker_run, monkeypatch):
    r = broker_run
    prepare_funding_review(r)

    def reconsider(*args):
        r.positions["EIX"] = 4
        return execution.ReviewDecision(action="propose_replacement", rationale="Smaller switch",
            rotation=dict(sell_ticker="EIX", sell_shares=5, buy_ticker="CCL", buy_shares=10))

    monkeypatch.setattr(execution, "compare_candidate", reconsider)
    r.run("CCL")
    r.broker.submit_order.assert_not_called()
    assert "Positions or open orders changed" in r.report["candidates"]["CCL"]["execution"]["reason"]


def test_only_legacy_unsubmitted_funding_failure_reopens():
    reason = "Estimated sale proceeds and free cash cannot fund the replacement"
    report = {"candidates": {
        "TRV": {"execution": {"state": "failed", "orders": {}, "reason": reason}},
        "CCL": {"execution": {"state": "incomplete_replacement", "orders": {"sell": {}}, "reason": reason}},
        "NEW": {"execution": {"state": "failed", "orders": {}, "reason": reason, "funding_reassessments": []}},
    }}
    execution.migrate_execution_records(report)
    assert [e["execution"]["state"] for e in report["candidates"].values()] == [
        "needs_review", "incomplete_replacement", "failed"]


@pytest.mark.parametrize("side,filled,state", [
    ("sell", "2", "incomplete_replacement"),
    ("buy", "0", "incomplete_replacement"),
    ("buy", "3", "incomplete_replacement"),
])
def test_partial_or_failed_rotation_remains_visible(broker_run, side, filled, state):
    r = broker_run
    r.add("CCL", rotation=True, quantity=10)
    r.run("CCL")
    sale = next(iter(r.orders.values()))
    if side == "buy":
        sale.status, sale.filled_qty = "filled", "5"
        r.positions["EIX"] = 0
        r.balance.cash = r.balance.buying_power = "330"
        r.run("CCL")
    order = next(o for o in r.orders.values() if o.side == side)
    order.status, order.filled_qty = "expired", filled
    r.run("CCL")
    result = r.report["candidates"]["CCL"]["execution"]
    assert result["state"] == state
    assert result["reserved_cash"] == "0"
    assert execution.report_status(r.report) == "needs_attention"
    assert "CCL" in {c["ticker"] for c in main.load_candidates(r.queue)}
    calls = r.broker.submit_order.call_count
    r.run("CCL")
    assert r.broker.submit_order.call_count == calls


def test_old_submitted_buy_is_reconciled_even_if_removed_from_queue(broker_run):
    r = broker_run
    r.balance.cash = r.balance.buying_power = "1000"
    r.add("COF")
    r.run("COF")
    main.complete_candidate("COF", r.queue)
    r.report["candidates"]["COF"]["execution"]["state"] = "complete"
    execution.migrate_execution_records(r.report)
    assert r.report["candidates"]["COF"]["execution"]["state"] == "active"
    order = next(iter(r.orders.values()))
    order.status = "rejected"
    r.run("COF")
    assert r.report["candidates"]["COF"]["execution"]["state"] == "failed"
    assert r.broker.submit_order.call_count == 1


def test_ambiguous_submit_recovered_by_id_without_resubmission(broker_run):
    r = broker_run
    r.balance.cash = r.balance.buying_power = "1000"
    r.add("COF")
    original = r.broker.submit_order.side_effect
    def accepted_then_disconnected(order_data):
        original(order_data)
        raise ConnectionError("response lost")
    r.broker.submit_order.side_effect = accepted_then_disconnected
    with pytest.raises(RuntimeError, match="uncertain"):
        r.run("COF")
    assert trading._pending_path().exists()
    order = next(iter(r.orders.values()))
    order.status, order.filled_qty = "filled", "1"
    r.report.update(json.loads(r.output.read_text()))
    r.run("COF")
    assert r.broker.submit_order.call_count == 1
    assert not trading._pending_path().exists()
    assert r.report["candidates"]["COF"]["execution"]["state"] == "complete"


def test_changed_positions_isolates_failure_and_other_candidate_can_trade(broker_run):
    r = broker_run
    r.balance.cash = r.balance.buying_power = "1000"
    r.add("CCL", rotation=True, quantity=10)
    r.positions["EIX"] = 4
    r.run("CCL")
    assert r.report["candidates"]["CCL"]["execution"]["state"] == "failed"
    r.add("COF")
    r.run("COF")
    assert [o.symbol for o in r.orders.values()] == ["COF"]


def test_sale_slippage_records_incomplete_rotation(broker_run):
    r = broker_run
    r.add("CCL", rotation=True, quantity=10)
    r.run("CCL")
    sale = next(iter(r.orders.values()))
    sale.status, sale.filled_qty = "filled", "5"
    r.positions["EIX"] = 0
    r.balance.cash = r.balance.buying_power = "250"
    r.run("CCL")
    assert len(r.orders) == 1
    result = r.report["candidates"]["CCL"]["execution"]
    assert result["state"] == "incomplete_replacement"
    assert result["reserved_cash"] == "0"
    assert "Not enough cash" in result["reason"]
    assert "CCL" in {c["ticker"] for c in main.load_candidates(r.queue)}


def test_http_rejection_does_not_stop_next_candidate(broker_run):
    r = broker_run
    class Rejected(Exception):
        status_code = 422
    r.balance.cash = r.balance.buying_power = "1000"
    r.add("CCL", quantity=1)
    normal_submit = r.broker.submit_order.side_effect
    r.broker.submit_order.side_effect = Rejected("rejected")
    r.run("CCL")
    assert r.report["candidates"]["CCL"]["execution"]["state"] == "failed"
    assert not trading._pending_path().exists()
    r.broker.submit_order.side_effect = normal_submit
    r.add("COF")
    r.run("COF")
    assert [o.symbol for o in r.orders.values()] == ["COF"]
