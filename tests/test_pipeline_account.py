import json
import sys
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src import main
from src.debate_agent import nodes
from src.debate_agent.schemas import Thesis
from src.decision_agent import agent, portfolio, trading


def decision_reasoning():
    return dict(rationale="Evidence supports the selected action.",
                decisive_evidence=["discovery: supplied research"],
                alternatives_rejected="Other actions have weaker support.",
                sizing_rationale="Limited size for uncertainty.",
                risks_and_uncertainties="Execution costs remain uncertain.",
                change_conditions="Reassess on changed fundamentals.")


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps({"candidates": [{"ticker": "AAPL"}, {"ticker": "MSFT"}]}))
    ledger = tmp_path / "portfolio.json"
    ledger.write_text('[{"ticker":"AAPL","number_of_stocks":999}]')
    monkeypatch.setattr(portfolio, "PORTFOLIO_PATH", ledger)
    client = MagicMock()
    balance = SimpleNamespace(buying_power="10000", cash="10000")
    client.get_account.return_value = balance
    client.get_orders.return_value = []
    client.get_all_positions.return_value = []
    client.get_clock.return_value = SimpleNamespace(is_open=True)
    monkeypatch.setattr(trading, "get_client", lambda: client)
    monkeypatch.setattr(trading, "get_latest_prices", lambda symbols: {"AAPL": Decimal("100")})
    monkeypatch.setitem(sys.modules, "src.supervisor.research", SimpleNamespace(
        gather_research_data=SimpleNamespace(invoke=lambda _: json.dumps(
            {"news_agent": "news", "economic_agent": "report", "finance_agent": "metrics"}
        ))
    ))
    debates = []
    decisions = []

    def debate(schema, prompt, payload):
        debates.append((payload["analysis_packet"]["ticker"], payload.get("account_snapshot")))
        if schema is Thesis:
            return schema(summary="Summary", arguments=[dict(claim="Claim", rationale="Reason",
                          evidence_ids=["discovery"], confidence=0.5)],
                          acknowledged_weaknesses=[], missing_information=[])
        return schema(responses=[dict(opposing_argument_id=payload["allowed_opposing_argument_ids"][0],
                      response="Response", evidence_ids=["discovery"], concession=False)],
                      revised_position="Position", conceded_points=[], unresolved_questions=[])

    def decide(messages):
        data = json.loads(messages[1][1])
        decisions.append(data)
        buy = data["ticker"] == "AAPL"
        return dict(ticker=data["ticker"], action="buy" if buy else "hold", number_of_stocks=5 if buy else 0,
                    reasoning=decision_reasoning())

    model = MagicMock()
    model.with_structured_output.return_value.invoke.side_effect = decide
    monkeypatch.setattr(agent, "get_model", lambda: model)
    monkeypatch.setattr(nodes, "_invoke", debate)
    return SimpleNamespace(queue=queue, client=client, balance=balance, debates=debates,
                           decisions=decisions, model=model, ledger=ledger)


@pytest.mark.parametrize("status,filled", [("filled", 5), ("partially_filled", 2), ("accepted", 0)])
def test_next_candidate_sees_previous_order(pipeline, status, filled):
    p = pipeline
    p.client.get_clock.return_value.is_open = status != "accepted"

    def submit(order_data):
        order = SimpleNamespace(id="order-1", symbol="AAPL", side="buy", qty="5",
                                notional=None, limit_price="102", filled_qty=str(filled), status=status,
                                client_order_id=order_data.client_order_id)
        p.balance.buying_power = "9500"
        p.balance.cash = str(10000 - 100 * filled)
        p.client.get_all_positions.return_value = [SimpleNamespace(symbol="AAPL", qty=str(filled))] if filled else []
        p.client.get_orders.return_value = [] if status == "filled" else [order]
        return order

    p.client.submit_order.side_effect = submit
    main.main(p.queue)
    aapl, msft = p.decisions
    assert aapl["current_number_of_stocks"] == 0
    snapshot = msft["account_snapshot"]
    assert snapshot["buying_power"] == "9500"
    assert snapshot["positions"] == ({"AAPL": str(filled)} if filled else {})
    assert snapshot["current_number_of_stocks"] == 0
    assert [(o["status"], o["qty"], o["filled_qty"]) for o in snapshot["open_orders"]] == (
        [] if status == "filled" else [(status, "5", str(filled))]
    )
    assert [s for ticker, s in p.debates if ticker == "MSFT"] == [snapshot] * 4
    assert json.loads(p.ledger.read_text())[0]["number_of_stocks"] == 999
    assert p.client.submit_order.call_count == 1


def test_restart_after_interrupted_queue_write(pipeline, monkeypatch):
    p = pipeline

    def submit(order_data):
        order = SimpleNamespace(id="order-1", symbol="AAPL", side="buy", qty="5",
                                notional=None, limit_price="102", filled_qty="0", status="accepted",
                                client_order_id=order_data.client_order_id)
        p.client.get_order_by_client_id.return_value = order
        p.client.get_orders.return_value = [order]
        return order

    p.client.submit_order.side_effect = submit
    with monkeypatch.context() as patch:
        patch.setattr(main, "complete_candidate", MagicMock(side_effect=OSError("interrupted")))
        with pytest.raises(OSError, match="interrupted"):
            main.main(p.queue)
    assert main.load_candidates(p.queue)[0]["ticker"] == "AAPL"
    main.main(p.queue)
    assert p.client.submit_order.call_count == 1
    p.client.get_order_by_client_id.assert_called_once()
    assert [d["ticker"] for d in p.decisions] == ["AAPL", "MSFT"]
    assert not main.load_candidates(p.queue)


def test_refresh_and_reassess_before_submission(pipeline, monkeypatch):
    p = pipeline
    original = nodes._invoke

    def debate(*args):
        if not p.decisions:
            p.balance.buying_power = "9000"
        return original(*args)

    monkeypatch.setattr(nodes, "_invoke", debate)
    invoke = p.model.with_structured_output.return_value.invoke
    original_decide = invoke.side_effect

    def decide(messages):
        result = original_decide(messages)
        if len(p.decisions) == 1:
            p.balance.buying_power = "400"
            return result
        return {**result, "action": "hold", "number_of_stocks": 0}

    invoke.side_effect = decide
    main.main(p.queue)
    assert p.debates[0][1]["buying_power"] == "10000"
    assert [d["account_snapshot"]["buying_power"] for d in p.decisions] == ["9000", "400", "400"]
    p.client.submit_order.assert_not_called()


def test_snapshot_unavailable_at_submit_preserves_queue(pipeline):
    p = pipeline
    p.client.get_all_positions.side_effect = [[], [], ConnectionError("positions unavailable")]
    with pytest.raises(ConnectionError, match="unavailable"):
        main.main(p.queue)
    assert [c["ticker"] for c in main.load_candidates(p.queue)] == ["AAPL", "MSFT"]
    p.client.submit_order.assert_not_called()


def test_json_toggle_uses_local_holdings_for_decisions(pipeline):
    p = pipeline
    def hold(messages):
        data = json.loads(messages[1][1])
        p.decisions.append(data)
        return dict(ticker=data["ticker"], action="hold", number_of_stocks=0)

    p.model.with_structured_output.return_value.invoke.side_effect = hold
    main.main(p.queue, portfolio_source="json")
    assert [d["current_number_of_stocks"] for d in p.decisions] == [999, 0]
    assert all("account_snapshot" not in d for d in p.decisions)
    p.client.get_all_positions.assert_not_called()
    p.client.submit_order.assert_not_called()

def test_msft_buy_tolerates_balance_drift(pipeline, monkeypatch):
    p = pipeline
    p.queue.write_text(json.dumps({"candidates": [{"ticker": "MSFT"}]}))
    position = SimpleNamespace(symbol="MSFT", qty="25")
    p.client.get_all_positions.return_value = [position]
    monkeypatch.setattr(trading, "get_latest_prices", lambda _: {"MSFT": Decimal("410")})

    def decide(messages):
        assert json.loads(messages[1][1])["current_number_of_stocks"] == 25
        p.balance.buying_power = "9999.98"
        position.qty = "25.000"
        return dict(ticker="MSFT", action="buy", number_of_stocks=5)

    invoke = p.model.with_structured_output.return_value.invoke
    invoke.side_effect = decide
    p.client.submit_order.side_effect = lambda order_data: SimpleNamespace(
        id="msft-order", symbol="MSFT", side="buy", status="accepted", filled_qty="0",
        client_order_id=order_data.client_order_id,
    )
    main.main(p.queue)
    invoke.assert_called_once()
    p.client.submit_order.assert_called_once()
    assert not main.load_candidates(p.queue)


@pytest.mark.parametrize("cash,last_price,submitted", [("724.27", "220.42", 3), ("100", "220.42", 0),
                                                        ("724.27", "300", 0)])
def test_review_debate_and_cash_guard(pipeline, monkeypatch, cash, last_price, submitted):
    from src.decision_agent import review

    p = pipeline
    p.queue.write_text(json.dumps({"candidates": [{"ticker": "DDOG"}, {"ticker": "MSFT"}]}))
    p.balance.cash = cash
    monkeypatch.setattr(review, "get_client", lambda: p.client)
    monkeypatch.setattr(review, "_assess", lambda packet: {"evidence_ids": ["discovery"]})
    prices = iter(["220.42", last_price])
    monkeypatch.setattr(trading, "get_latest_prices", lambda symbols: {
        s: Decimal(next(prices) if s == "DDOG" else "100") for s in symbols
    })

    def decide(messages):
        payload = json.loads(messages[1][1])
        ticker = payload["ticker"]
        research = json.loads(payload["research"])
        assert all(research[k] for k in ("bull_analysis", "bear_analysis", "bull_rebuttal", "bear_rebuttal"))
        assert research["max_cash_buy_shares"] == (int(Decimal(cash) // Decimal("224.82"))
                                                    if ticker == "DDOG" else int(Decimal(cash) // 102))
        return {"ticker": ticker, "action": "buy" if ticker == "DDOG" else "hold",
                "number_of_stocks": 20 if ticker == "DDOG" else 0,
                "reasoning": decision_reasoning()}

    p.model.with_structured_output.return_value.invoke.side_effect = decide
    def compare(ticker, assessment, holdings, snapshot):
        assert ticker == "DDOG" and assessment["debate"]["bear_rebuttal"]
        return review.ReviewDecision(action="buy_with_cash", cash_buy_shares=20, rationale="test", rotation=None)
    monkeypatch.setattr(review, "compare_candidate", compare)
    p.client.submit_order.side_effect = lambda order_data: SimpleNamespace(
        symbol="DDOG", side="buy", status="filled", filled_qty=str(order_data.qty), id="test",
        client_order_id=order_data.client_order_id)
    main.main(p.queue, execute_review_all=True)
    assert [s for s, _ in p.debates] == ["DDOG"] * 4 + ["MSFT"] * 4
    if submitted:
        p.client.submit_order.assert_called_once()
        assert p.client.submit_order.call_args.kwargs["order_data"].qty == submitted
    else:
        p.client.submit_order.assert_not_called()
    assert [c["ticker"] for c in main.load_candidates(p.queue)] == (["DDOG"] if last_price == "300" else [])


def test_pre_debate_rotation_resumes_without_unreviewed_buy(pipeline, monkeypatch):
    from src.decision_agent import review
    p = pipeline
    p.queue.write_text('{"candidates":[{"ticker":"MSFT"}]}')
    position = SimpleNamespace(symbol="ORCL", qty="15")
    p.client.get_all_positions.return_value = [position]
    order = SimpleNamespace(symbol="ORCL", side="sell", id="old-sale", status="accepted",
                            filled_qty="0", client_order_id="old-client-id")
    p.client.get_order_by_client_id.return_value = order
    monkeypatch.setattr(review, "get_client", lambda: p.client)
    monkeypatch.setattr(review, "_assess", lambda _: {"investment_case": "test"})
    monkeypatch.setattr(trading, "get_latest_prices", lambda _: {"MSFT": Decimal("100")})
    rotation = dict(sell_ticker="ORCL", sell_shares=15, buy_ticker="MSFT", buy_shares=3)
    entry = dict(snapshot=trading.account_snapshot("MSFT"), action="propose_replacement",
                 rationale="legacy", rotation=rotation, execution=dict(state="active", orders={
                     "sell": dict(client_order_id="old-client-id", status="accepted")}))
    report = p.queue.parent / "holdings_review.json"
    main.save_json(report, dict(mode="paper_queue", status="awaiting_sales", as_of="2026-11-03",
                                queue_source=str(p.queue), holdings={}, candidates={"MSFT": entry}))
    def fill(seconds):
        if seconds == 30:
            order.status, order.filled_qty = "filled", "15"
            p.client.get_all_positions.return_value = []
    monkeypatch.setattr(main, "sleep", fill)
    main.main(p.queue, execute_review_all=True)
    assert [s for s, _ in p.debates] == ["MSFT"] * 4
    assert json.loads(report.read_text())["candidates"]["MSFT"]["risk_decision"]["action"] == "hold"
    assert not main.load_candidates(p.queue)
    p.client.submit_order.assert_not_called()
