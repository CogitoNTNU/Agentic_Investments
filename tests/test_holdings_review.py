import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src import main
from src.decision_agent.schemas import Decision
from src.decision_agent import review, trading


@pytest.fixture
def buy_gate(monkeypatch):
    def approve(packet, holdings, report=None):
        ticker = packet["ticker"]
        return {}, Decision(ticker=ticker, action="buy", number_of_stocks=5), review.account_snapshot(ticker), 5
    monkeypatch.setattr(review, "debate_risk_decision", approve)


@pytest.mark.parametrize("remaining,propose,invalid", [
    (10, True, False), (0, False, False), (0, True, True),
])
def test_holdings_first_review(monkeypatch, tmp_path, remaining, propose, invalid, buy_gate):
    queue = tmp_path / "sigurd.json"
    queue.write_text('{"candidates":[{"ticker":"NVDA"},{"ticker":"MSFT"}]}')
    original = queue.read_bytes()
    output = tmp_path / "holdings_review.json"
    broker = MagicMock()
    monkeypatch.setattr(review, "get_client", lambda: broker)
    monkeypatch.setattr(trading, "get_client", lambda: broker)
    broker.get_all_positions.side_effect = [
        [SimpleNamespace(symbol="MSFT", qty="25")],
        *([[SimpleNamespace(symbol="MSFT", qty=str(remaining))] if remaining else []] * 4),
    ]
    broker.get_account.return_value = SimpleNamespace(cash="20000", buying_power="80000")
    broker.get_orders.return_value = [
        SimpleNamespace(id="open-sale", symbol="MSFT", side="sell", status="partially_filled",
                        qty="5", filled_qty="2", notional=None, limit_price=None)
    ] if remaining else []
    researched = []

    def research(candidate):
        ticker = candidate["ticker"]
        researched.append(ticker)
        if ticker == "NVDA":
            saved = json.loads(output.read_text())
            assert saved["holdings"]["MSFT"]["weaknesses"] == "MSFT demand weakened"
            assert saved["status"] == "holdings_reviewed"
        return {"ticker": ticker, "evidence": [{"id": "economic_agent"}]}

    monkeypatch.setattr(main, "research_candidate", research)
    rotation = dict(sell_ticker="MSFT", sell_shares=5, buy_ticker="NVDA", buy_shares=2)
    model = MagicMock()
    monkeypatch.setattr(review, "get_model", lambda: model)

    def respond(messages):
        data = json.loads(messages[1][1])
        if "evidence" in data:
            return dict(investment_case="Long-term demand", weaknesses=data["ticker"] + " demand weakened",
                        trim_or_exit_conditions="Two quarters of weaker demand", evidence_ids=["economic_agent"])
        nvda = data["candidate_ticker"] == "NVDA"
        assert data["sellable_shares"] == ({"MSFT": remaining - 3} if remaining and nvda else {})
        assert data["account_snapshot"]["cash"] == "20000"
        if remaining:
            assert data["holdings"]["MSFT"]["weaknesses"] == "MSFT demand weakened"
        else:
            assert not data["holdings"]
        replace = propose and nvda
        return dict(action="propose_replacement" if replace else ("buy_with_cash" if nvda else "pass"),
                    cash_buy_shares=2 if nvda and not replace else 0,
                    rationale="Compare MSFT demand with NVDA growth", rotation=rotation if replace else None)

    model.with_structured_output.return_value.invoke.side_effect = respond
    if invalid:
        with pytest.raises(ValueError, match="available holdings"):
            main.main(queue, review_portfolio=True)
        assert json.loads(output.read_text())["status"] == "holdings_reviewed"
    else:
        main.main(queue, review_portfolio=True)
        report = json.loads(output.read_text())
        assert report["status"] == "complete"
        assert report["candidates"]["NVDA"]["rotation"] == (rotation if propose else None)
        assert report["candidates"]["NVDA"]["action"] == ("propose_replacement" if propose else "buy_with_cash")
        assert report["candidates"]["MSFT"]["action"] == "pass"
    assert researched == ["MSFT", "NVDA"]
    assert queue.read_bytes() == original
    broker.submit_order.assert_not_called()


@pytest.mark.parametrize("action", ["pass", "buy_with_cash", "propose_replacement"])
def test_execute_selected_review(monkeypatch, tmp_path, action):
    from decimal import Decimal
    from src.decision_agent import portfolio

    queue = tmp_path / "queue.json"
    queue.write_text('{"candidates":[{"ticker":"NVDA"},{"ticker":"AAPL"}]}')
    monkeypatch.setattr(portfolio, "PORTFOLIO_PATH", tmp_path / "portfolio.json")
    broker = MagicMock()
    monkeypatch.setattr(trading, "get_client", lambda: broker)
    monkeypatch.setattr(trading, "get_latest_prices", lambda symbols: {s: Decimal("100") for s in symbols})
    position = SimpleNamespace(symbol="MSFT", qty="25")
    broker.get_all_positions.return_value = [position]
    broker.get_account.return_value = SimpleNamespace(cash="1000", buying_power="4000")
    broker.get_orders.return_value = []
    broker.get_clock.return_value = SimpleNamespace(is_open=True)
    orders = {}

    def submit(order_data):
        sell = order_data.side == "sell"
        order = SimpleNamespace(client_order_id=order_data.client_order_id, symbol=order_data.symbol,
                                side=order_data.side, id=str(len(orders)), filled_qty="1" if sell else "0",
                                status="partially_filled" if sell else "accepted")
        orders[order.client_order_id] = order
        return order

    broker.submit_order.side_effect = submit
    broker.get_order_by_client_id.side_effect = orders.__getitem__
    report = tmp_path / "holdings_review.json"
    rotation = dict(buy_ticker="NVDA", buy_shares=2, sell_ticker="MSFT", sell_shares=5)
    entry = dict(action=action, rationale="test", risk_decision={"action": "buy"}, snapshot=trading.account_snapshot("NVDA"),
                 rotation=rotation if action == "propose_replacement" else None,
                 cash_buy_shares=2 if action == "buy_with_cash" else 0)
    main.save_json(report, dict(status="complete", queue_source=str(queue), candidates={"NVDA": entry}))
    main.main(queue, execute_review="NVDA")
    if action == "propose_replacement":
        assert [o.side for o in orders.values()] == ["sell"]
        main.main(queue, execute_review="NVDA")
        assert len(orders) == 1
        sell = next(iter(orders.values()))
        sell.status, sell.filled_qty, position.qty = "filled", "5", "20"
        main.main(queue, execute_review="NVDA")
    if action != "pass":
        buy = next(o for o in orders.values() if o.side == "buy")
        assert json.loads(report.read_text())["candidates"]["NVDA"]["execution"]["state"] == "active"
        buy.status, buy.filled_qty = "filled", "2"
    main.main(queue, execute_review="NVDA")
    sides = {"pass": [], "buy_with_cash": ["buy"], "propose_replacement": ["sell", "buy"]}
    assert [o.side for o in orders.values()] == sides[action]
    assert broker.submit_order.call_count == len(sides[action])
    assert [c["ticker"] for c in main.load_candidates(queue)] == ["AAPL"]
    assert json.loads(report.read_text())["candidates"]["NVDA"]["execution"]["state"] == "complete"


def test_execute_all_resumes_rotation_then_trades_next_candidate(monkeypatch, tmp_path, buy_gate):
    from decimal import Decimal
    from src.decision_agent import portfolio

    queue = tmp_path / "sigurd.json"
    queue.write_text('{"candidates":[{"ticker":"NVDA"},{"ticker":"AAPL"}]}')
    monkeypatch.setattr(portfolio, "PORTFOLIO_PATH", tmp_path / "portfolio.json")
    broker = MagicMock()
    monkeypatch.setattr(review, "get_client", lambda: broker)
    monkeypatch.setattr(trading, "get_client", lambda: broker)
    monkeypatch.setattr(trading, "get_latest_prices", lambda symbols: {s: Decimal(100) for s in symbols})
    positions = {"MSFT": 25}
    broker.get_all_positions.side_effect = lambda: [SimpleNamespace(symbol=s, qty=str(q)) for s, q in positions.items()]
    broker.get_account.return_value = SimpleNamespace(cash="1000", buying_power="1000")
    broker.get_orders.return_value = []
    broker.get_clock.return_value = SimpleNamespace(is_open=True)
    monkeypatch.setattr(main, "research_candidate", lambda c: c)
    monkeypatch.setattr(review, "_assess", lambda packet: {"ticker": packet["ticker"]})
    decisions = []

    def choose(ticker, assessment, holdings, snapshot):
        decisions.append(ticker)
        if ticker == "NVDA":
            return review.ReviewDecision(action="propose_replacement", rationale="test",
                rotation=review.Rotation(buy_ticker=ticker, buy_shares=2, sell_ticker="MSFT", sell_shares=5))
        assert snapshot["positions"] == {"MSFT": "24"}
        return review.ReviewDecision(action="buy_with_cash", cash_buy_shares=1, rationale="test", rotation=None)

    monkeypatch.setattr(review, "compare_candidate", choose)
    orders = {}

    def submit(order_data):
        sell = order_data.side == "sell"
        filled = 1 if sell else int(order_data.qty)
        positions[order_data.symbol] = positions.get(order_data.symbol, 0) + (-filled if sell else filled)
        order = SimpleNamespace(client_order_id=order_data.client_order_id, symbol=order_data.symbol,
                                side=order_data.side, id=str(len(orders)), filled_qty=str(filled),
                                status="partially_filled" if sell else "filled")
        orders[order.client_order_id] = order
        return order

    broker.submit_order.side_effect = submit
    broker.get_order_by_client_id.side_effect = orders.__getitem__
    polls = []

    def wait(seconds):
        # Ignore the short retries used for atomic Windows file writes.
        if seconds != 30:
            return
        polls.append(seconds)
        assert decisions == ["NVDA", "AAPL"]
        assert len(orders) == 2
        assert [c["ticker"] for c in main.load_candidates(queue)] == ["NVDA"]
        if len(polls) == 2:
            sale = next(iter(orders.values()))
            sale.status, sale.filled_qty, positions["MSFT"] = "filled", "5", 20
        assert len(polls) <= 2

    monkeypatch.setattr(main, "sleep", wait)
    main.main(queue, execute_review_all=True)
    assert polls == [30, 30]
    assert [o.symbol for o in orders.values()] == ["MSFT", "AAPL", "NVDA"]
    assert portfolio.read_portfolio() == [
        {"ticker": "AAPL", "number_of_stocks": 1},
        {"ticker": "MSFT", "number_of_stocks": 20},
        {"ticker": "NVDA", "number_of_stocks": 2},
    ]
    assert not main.load_candidates(queue)
    report = json.loads((tmp_path / "holdings_review.json").read_text())
    assert report["status"] == "complete"
    assert all(c["execution"]["state"] == "complete" for c in report["candidates"].values())


def test_interrupted_holdings_pass_resumes_per_holding(monkeypatch, tmp_path, buy_gate):
    queue = tmp_path / "sigurd.json"
    queue.write_text('{"candidates":[{"ticker":"NVDA"}]}')
    broker = MagicMock()
    broker.get_all_positions.return_value = [SimpleNamespace(symbol=s, qty="2") for s in ["AAPL", "MSFT"]]
    monkeypatch.setattr(review, "get_client", lambda: broker)
    from src.decision_agent import portfolio
    monkeypatch.setattr(trading, "get_client", lambda: broker)
    monkeypatch.setattr(portfolio, "PORTFOLIO_PATH", tmp_path / "portfolio.json")
    calls = []

    def research(candidate):
        calls.append(candidate["ticker"])
        if calls == ["AAPL", "MSFT"]:
            raise KeyboardInterrupt
        return candidate

    monkeypatch.setattr(main, "research_candidate", research)
    monkeypatch.setattr(review, "_assess", lambda packet: {"investment_case": packet["ticker"]})
    monkeypatch.setattr(review, "account_snapshot", lambda _: {"positions": {}, "open_orders": []})
    monkeypatch.setattr(review, "compare_candidate", lambda *args: review.ReviewDecision(
        action="pass", rationale="test", rotation=None))
    with pytest.raises(KeyboardInterrupt):
        main.main(queue, execute_review_all=True)
    report = tmp_path / "holdings_review.json"
    partial = json.loads(report.read_text())
    assert partial["status"] == "reviewing_holdings"
    assert list(partial["holdings"]) == ["AAPL"]
    monkeypatch.setattr(trading, "sync_pending_order", lambda: None)
    main.main(queue, execute_review_all=True)
    assert calls == ["AAPL", "MSFT", "MSFT", "NVDA"]
    assert json.loads(report.read_text())["status"] == "complete"
    broker.submit_order.assert_not_called()


def test_cash_shortfall_compares_trim_before_reducing_buy(monkeypatch):
    from decimal import Decimal
    rotation = review.Rotation(sell_ticker="MSFT", sell_shares=8, buy_ticker="DDOG", buy_shares=20)
    monkeypatch.setattr(trading, "get_latest_prices", lambda symbols: {"MSFT": Decimal("500")})

    def evaluate(schema, prompt, payload):
        assert payload["funding"] == {"desired_shares": 20, "cash_only_shares": 3,
                                     "shares_needing_sale_proceeds": 17,
                                     "estimated_sale_price_per_share": {"MSFT": "500"}}
        assert payload["sellable_shares"] == {"MSFT": 25}
        return schema(action="propose_replacement", rationale="MSFT thesis weakened", rotation=rotation)

    monkeypatch.setattr(review, "_ask", evaluate)
    result = review.compare_candidate("DDOG", {"decision": {"number_of_stocks": 20},
                                      "max_cash_buy_shares": 3}, {"MSFT": {"weaknesses": "Demand"}},
                                      {"positions": {"MSFT": "25"}, "open_orders": []})
    assert result.rotation == rotation


def test_funding_reassessment_supplies_conservative_affordable_limits(monkeypatch):
    from decimal import Decimal
    monkeypatch.setattr(trading, "get_latest_prices", lambda symbols: {s: Decimal("60") for s in symbols})

    def evaluate(schema, prompt, payload):
        funding = payload["funding"]
        assert funding["conservative_sale_price_per_share"] == {"EIX": "58.80"}
        assert funding["max_buy_shares_if_entire_sellable_holding_sold"] == {"EIX": 10}
        assert payload["candidate_assessment"]["debate"] == {"bear_analysis": "risks"}
        return schema(action="pass", rationale="Switch not worthwhile", rotation=None)

    monkeypatch.setattr(review, "_ask", evaluate)
    review.compare_candidate("CCL", {"decision": {"number_of_stocks": 20},
        "max_cash_buy_shares": 1, "debate": {"bear_analysis": "risks"},
        "funding_reassessment": {"buy_limit_price": "29.58", "free_cash": "30"}},
        {"EIX": {}}, {"positions": {"EIX": "5"}, "open_orders": []})

