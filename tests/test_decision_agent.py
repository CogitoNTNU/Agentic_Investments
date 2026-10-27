import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.decision_agent import agent, portfolio, trading
from src.decision_agent.schemas import Decision


@pytest.fixture
def portfolio_path(monkeypatch, tmp_path):
    path = tmp_path / "portfolio.json"
    monkeypatch.setattr(portfolio, "PORTFOLIO_PATH", path)
    client = MagicMock()
    client.get_all_positions.side_effect = lambda: [
        SimpleNamespace(symbol=p["ticker"], qty=str(p["number_of_stocks"]))
        for p in portfolio.read_portfolio()
    ]
    client.submit_order.side_effect = lambda order_data: SimpleNamespace(
        id="test-order",
        client_order_id=order_data.client_order_id,
        symbol=order_data.symbol,
        side=order_data.side,
        status="filled",
        filled_qty=str(int(order_data.qty)),
    )
    monkeypatch.setattr(trading, "get_client", lambda: client)
    return path


def fake_model(monkeypatch, response):
    model = MagicMock()
    model.with_structured_output.return_value.invoke.return_value = response
    monkeypatch.setattr(agent, "get_model", lambda: model)
    return model


def test_buy_add_sell_and_remove_preserves_other_stocks(portfolio_path):
    for ticker, action, quantity, before in [
        ("MSFT", "buy", 2, 0),
        ("AAPL", "buy", 10, 0),
        ("AAPL", "buy", 3, 10),
        ("AAPL", "sell", 5, 13),
        ("AAPL", "sell", 8, 8),
    ]:
        portfolio.apply_decision(
            Decision(ticker=ticker, action=action, number_of_stocks=quantity), before
        )
    assert portfolio.get_number_of_stocks(" aapl ") == 0
    assert json.loads(portfolio_path.read_text()) == [
        {"ticker": "MSFT", "number_of_stocks": 2}
    ]


@pytest.mark.parametrize(
    "data", ["Free form research", {"anything": [1, 2]}, [42], None]
)
def test_arbitrary_research_and_fixed_output(monkeypatch, portfolio_path, data):
    response = {"ticker": "AAPL", "action": "buy", "number_of_stocks": 3}
    model = fake_model(monkeypatch, response)
    assert agent.run_decision(data, " aapl ") == response
    model.with_structured_output.assert_called_once_with(Decision)
    payload = json.loads(
        model.with_structured_output.return_value.invoke.call_args.args[0][1][1]
    )
    assert payload["ticker"] == "AAPL"
    assert payload["current_number_of_stocks"] == 0
    assert portfolio.get_number_of_stocks("AAPL") == 3


@pytest.mark.parametrize(
    "response",
    [
        {"ticker": "AAPL", "action": "buy", "number_of_stocks": -1},
        {"ticker": "AAPL", "action": "buy", "number_of_stocks": 1.5},
        {"ticker": "AAPL", "action": "buy", "number_of_stocks": True},
        {"ticker": "AAPL", "action": "buy", "number_of_stocks": "3"},
        {"ticker": "AAPL", "action": "buy", "number_of_stocks": 0},
        {"ticker": "AAPL", "action": "hold", "number_of_stocks": 1},
        {"ticker": "AAPL", "action": "invest", "number_of_stocks": 2},
        {"ticker": "MSFT", "action": "buy", "number_of_stocks": 2},
        {"ticker": "AAPL", "action": "sell", "number_of_stocks": 3},
        {"ticker": "AAPL", "action": "buy"},
    ],
)
def test_invalid_decisions_do_not_change_file(monkeypatch, portfolio_path, response):
    portfolio_path.write_text("[]\n", encoding="utf-8")
    before = portfolio_path.read_bytes()
    fake_model(monkeypatch, response)
    with pytest.raises(ValueError):
        agent.run_decision("research", "AAPL")
    assert portfolio_path.read_bytes() == before


def test_hold_and_model_failure_preserve_portfolio(monkeypatch, portfolio_path):
    portfolio_path.write_text('[{"ticker":"AAPL","number_of_stocks":5}]')
    before = portfolio_path.read_bytes()
    model = fake_model(
        monkeypatch, Decision(ticker="AAPL", action="hold", number_of_stocks=0)
    )
    agent.run_decision("research", "AAPL")
    assert portfolio_path.read_bytes() == before
    model.with_structured_output.return_value.invoke.side_effect = RuntimeError(
        "unavailable"
    )
    with pytest.raises(RuntimeError, match="unavailable"):
        agent.run_decision("research", "AAPL")
    assert portfolio_path.read_bytes() == before


@pytest.mark.parametrize(
    "contents",
    [
        "{broken",
        "{}",
        '[{"ticker":"AAPL","number_of_stocks":-2}]',
        '[{"ticker":"AAPL","number_of_stocks":1},{"ticker":"aapl","number_of_stocks":2}]',
    ],
)
def test_malformed_portfolio_is_not_overwritten(portfolio_path, contents):
    portfolio_path.write_text(contents)
    with pytest.raises(ValueError):
        portfolio.get_number_of_stocks("AAPL")
    assert portfolio_path.read_text() == contents


def test_stale_holding_is_rejected(portfolio_path):
    portfolio_path.write_text('[{"ticker":"AAPL","number_of_stocks":5}]')
    decision = Decision(ticker="AAPL", action="buy", number_of_stocks=1)
    with pytest.raises(ValueError, match="Holding changed"):
        portfolio.apply_decision(decision, expected_number_of_stocks=4)
    assert portfolio.get_number_of_stocks("AAPL") == 5


def test_failed_replace_preserves_portfolio(monkeypatch, portfolio_path):
    from pathlib import Path

    portfolio_path.write_text("[]")

    def fail_replace(*args):
        raise OSError("write failed")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="write failed"):
        portfolio.apply_decision(
            Decision(ticker="AAPL", action="buy", number_of_stocks=2), 0
        )
    assert portfolio_path.read_text() == "[]"
    assert list(portfolio_path.parent.glob("*.tmp")) == []


def test_debate_loads_holding_then_decides_and_sells(monkeypatch, portfolio_path):
    from src.debate_agent import nodes
    from src.debate_agent.graph import graph
    from src.debate_agent.schemas import Thesis

    portfolio_path.write_text('[{"ticker":"AAPL","number_of_stocks":5}]')

    def debate_response(schema, prompt, payload):
        if schema is Thesis:
            return schema(
                summary="Summary",
                arguments=[
                    {
                        "claim": "Claim",
                        "rationale": "Reason",
                        "evidence_ids": ["E1"],
                        "confidence": 0.5,
                    }
                ],
                acknowledged_weaknesses=[],
                missing_information=[],
            )
        return schema(
            responses=[
                {
                    "opposing_argument_id": payload["allowed_opposing_argument_ids"][0],
                    "response": "Response",
                    "evidence_ids": ["E1"],
                    "concession": False,
                }
            ],
            revised_position="Position",
            conceded_points=[],
            unresolved_questions=[],
        )

    monkeypatch.setattr(nodes, "_invoke", debate_response)
    model = fake_model(
        monkeypatch, {"ticker": "AAPL", "action": "sell", "number_of_stocks": 5}
    )
    states = list(
        graph.stream(
            {
                "analysis_packet": {
                    "ticker": "AAPL",
                    "company_name": "Apple",
                    "as_of": "2026-10-27",
                    "time_horizon": "1 year",
                    "evidence": [
                        {
                            "id": "E1",
                            "category": "financial",
                            "statement": "Declining revenue",
                            "source": "Synthetic",
                            "as_of": "2026-10-27",
                        }
                    ],
                }
            },
            stream_mode="values",
        )
    )
    loaded = next(state for state in states if "number_of_stocks" in state)
    assert loaded["number_of_stocks"] == 5
    assert "bull_analysis" not in loaded
    final = states[-1]
    assert final["decision"] == {
        "ticker": "AAPL",
        "action": "sell",
        "number_of_stocks": 5,
    }
    assert final["number_of_stocks"] == 0
    assert portfolio.read_portfolio() == []
    payload = json.loads(
        model.with_structured_output.return_value.invoke.call_args.args[0][1][1]
    )
    assert payload["current_number_of_stocks"] == 5
    assert "debate_report" in json.loads(payload["research"])
