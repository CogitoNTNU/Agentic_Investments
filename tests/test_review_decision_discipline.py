import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.decision_agent import agent, review, trading
from src.decision_agent.schemas import Decision, ExplainedDecision, ReviewDecisionResponse


def explanation():
    return dict(rationale="Valuation risk now outweighs the expected benefit.",
                decisive_evidence=["economic_agent: declining margins"],
                alternatives_rejected="Full exit is not justified by the evidence.",
                sizing_rationale="A small trim retains exposure to the intact thesis.",
                risks_and_uncertainties="Growth could recover; spread and fees are unknown.",
                change_conditions="Reassess if margins recover in the next filing.")


def snapshot():
    return dict(positions={"AAPL": "10"}, current_number_of_stocks=10, cash="1000",
                available_cash="100", buying_power="100000", open_orders=[],
                position_details={"AAPL": {"avg_entry_price": "80"}})


def test_market_context_uses_equity_not_available_cash_or_margin(monkeypatch):
    monkeypatch.setattr(trading, "get_latest_prices", lambda symbols: {
        "AAPL": Decimal("100"), "MSFT": Decimal("200")})
    context = review.market_context("MSFT", snapshot())
    assert context["estimated_equity"] == "2000"
    assert Decimal(context["holdings"]["AAPL"]["weight_pct"]) == 50
    assert Decimal(context["holdings"]["AAPL"]["unrealized_return_pct"]) == 25
    assert "MSFT" not in context["holdings"]
    assert context["prices"]["MSFT"] == "200"


@pytest.mark.parametrize("prices", [{}, {"AAPL": Decimal("NaN")}, {"AAPL": Decimal("0")}])
def test_missing_or_invalid_prices_stop_sizing(monkeypatch, prices):
    monkeypatch.setattr(trading, "get_latest_prices", lambda symbols: prices)
    with pytest.raises(ValueError, match="broker price"):
        review.market_context("AAPL", snapshot())


def test_missing_cost_basis_does_not_invent_profit(monkeypatch):
    monkeypatch.setattr(trading, "get_latest_prices", lambda symbols: {"AAPL": Decimal("100")})
    account = snapshot()
    account.pop("position_details")
    context = review.market_context("AAPL", account)
    assert "unrealized_return_pct" not in context["holdings"]["AAPL"]


@pytest.mark.parametrize("action,quantity", [("buy", 2), ("sell", 3), ("hold", 0)])
def test_review_requires_and_logs_reasoning_without_changing_order_schema(monkeypatch, capsys, action, quantity):
    response = dict(ticker="AAPL", action=action, number_of_stocks=quantity, reasoning=explanation())
    model = MagicMock()
    model.with_structured_output.return_value.invoke.return_value = response
    monkeypatch.setattr(agent, "get_model", lambda: model)
    result = agent.recommend_decision({}, "AAPL", 10, snapshot(), review_rotation=True)
    model.with_structured_output.assert_called_once_with(ReviewDecisionResponse, method="function_calling")
    assert result.reasoning.rationale == explanation()["rationale"]
    assert explanation()["rationale"] in capsys.readouterr().out
    assert result.model_dump() == dict(ticker="AAPL", action=action, number_of_stocks=quantity)
    assert Decision.model_validate(result.model_dump()).action == action


def test_review_rejects_unexplained_hold(monkeypatch):
    model = MagicMock()
    model.with_structured_output.return_value.invoke.return_value = dict(
        ticker="AAPL", action="hold", number_of_stocks=0)
    monkeypatch.setattr(agent, "get_model", lambda: model)
    with pytest.raises(ValueError, match="rationale"):
        agent.recommend_decision({}, "AAPL", 10, snapshot(), review_rotation=True)


@pytest.mark.parametrize("action,quantity", [("hold", 0), ("buy", 2), ("sell", 3)])
def test_real_tool_parser_accepts_flat_explanation_and_encoded_evidence(action, quantity):
    from langchain_core.messages import AIMessage
    from langchain_core.output_parsers.openai_tools import PydanticToolsParser

    flat = dict(ticker="AAPL", action=action, number_of_stocks=quantity, **explanation())
    flat["decisive_evidence"] = json.dumps(flat["decisive_evidence"])
    message = AIMessage(content="", tool_calls=[
        dict(name="ExplainedDecision", args=flat, id="test-call", type="tool_call")])
    parsed = PydanticToolsParser(tools=[ExplainedDecision], first_tool_only=True).invoke(message)
    assert parsed.reasoning.model_dump() == explanation()
    assert parsed.model_dump() == dict(ticker="AAPL", action=action, number_of_stocks=quantity)
    assert "reasoning" not in flat  # Parsing must not mutate the original response.


@pytest.mark.parametrize("changes", [
    {"number_of_stocks": 1},  # HOLD still requires zero.
    {"number_of_stocks": "0"},
    {"unexpected_field": "do not discard me"},
    {"decisive_evidence": "ordinary prose, not a list"},
    {"decisive_evidence": "[]"},
    {"decisive_evidence": '[123]'},
    {"reasoning": explanation()},  # Ambiguous nested and flat fields are rejected.
])
def test_format_repair_keeps_validation_strict(changes):
    flat = dict(ticker="AAPL", action="hold", number_of_stocks=0, **explanation())
    flat.update(changes)
    with pytest.raises(ValueError):
        ExplainedDecision.model_validate(flat)


def test_partial_flat_explanation_still_rejected():
    with pytest.raises(ValueError, match="change_conditions"):
        flat = dict(ticker="AAPL", action="hold", number_of_stocks=0, **explanation())
        flat.pop("change_conditions")
        ExplainedDecision.model_validate(flat)


def test_misnested_ticker_and_missing_rationale_repaired_by_model(monkeypatch):
    from langchain_core.messages import AIMessage
    from langchain_core.output_parsers.openai_tools import PydanticToolsParser

    bad_reasoning = {**explanation(), "ticker": "AAPL"}
    bad_reasoning.pop("rationale")
    malformed = dict(action="hold", number_of_stocks=0, reasoning=bad_reasoning)
    valid = dict(ticker="AAPL", action="hold", number_of_stocks=0, reasoning=explanation())
    parser = PydanticToolsParser(tools=[ReviewDecisionResponse], first_tool_only=True)
    calls = []

    def invoke(messages):
        calls.append(messages)
        args = malformed if len(calls) == 1 else dict(
            ticker="AAPL", action="hold", number_of_stocks=0, **explanation())
        return parser.invoke(AIMessage(content="", tool_calls=[
            dict(name="ReviewDecisionResponse", args=args, id="test-call", type="tool_call")]))

    model = MagicMock()
    model.with_structured_output.return_value.invoke.side_effect = invoke
    monkeypatch.setattr(agent, "get_model", lambda: model)
    result = agent.recommend_decision({"debate": "saved evidence"}, "AAPL", 10, snapshot(), review_rotation=True)
    assert len(calls) == 2
    assert calls[1][:2] == calls[0]  # Reuse original research; only redo decision.
    correction = json.loads(calls[1][-1][1])
    assert {"ticker", "rationale", "reasoning"} <= {
        e["field"] for e in correction["validation_errors"]}
    assert result.reasoning.model_dump() == explanation()


def test_invalid_decisions_exhaust_two_corrections_without_execution(monkeypatch):
    model = MagicMock()
    model.with_structured_output.return_value.invoke.return_value = dict(
        ticker="AAPL", action="buy", number_of_stocks=2)
    monkeypatch.setattr(agent, "get_model", lambda: model)
    execute = MagicMock()
    monkeypatch.setattr(agent, "execute_decision", execute)
    with pytest.raises(ValueError, match="rationale"):
        agent.recommend_decision({}, "AAPL", 10, snapshot(), review_rotation=True)
    assert model.with_structured_output.return_value.invoke.call_count == 3
    execute.assert_not_called()


def test_network_errors_are_not_format_retries(monkeypatch):
    model = MagicMock()
    model.with_structured_output.return_value.invoke.side_effect = ConnectionError("offline")
    monkeypatch.setattr(agent, "get_model", lambda: model)
    with pytest.raises(ConnectionError):
        agent.recommend_decision({}, "AAPL", 10, snapshot(), review_rotation=True)
    assert model.with_structured_output.return_value.invoke.call_count == 1


def test_model_tool_schema_has_nine_required_flat_fields():
    from langchain_core.utils.function_calling import convert_to_openai_tool

    parameters = convert_to_openai_tool(ReviewDecisionResponse)["function"]["parameters"]
    expected = {"ticker", "action", "number_of_stocks", *explanation()}
    assert set(parameters["properties"]) == expected
    assert set(parameters["required"]) == expected
    assert parameters["properties"]["decisive_evidence"]["type"] == "array"
    assert all(p.get("type") != "object" for p in parameters["properties"].values())


@pytest.mark.parametrize("action,quantity", [("hold", 0), ("buy", 1), ("sell", 2)])
def test_flat_tool_response_converts_to_existing_report_and_order_format(action, quantity):
    from langchain_core.messages import AIMessage
    from langchain_core.output_parsers.openai_tools import PydanticToolsParser

    args = dict(ticker="GS", action=action, number_of_stocks=quantity, **explanation())
    args["decisive_evidence"] = json.dumps(args["decisive_evidence"])
    result = PydanticToolsParser(tools=[ReviewDecisionResponse], first_tool_only=True).invoke(
        AIMessage(content="", tool_calls=[dict(name="ReviewDecisionResponse", args=args,
                                              id="flat-call", type="tool_call")]))
    decision = result.to_decision()
    assert decision.reasoning.model_dump() == explanation()
    assert decision.model_dump() == dict(ticker="GS", action=action, number_of_stocks=quantity)


def test_free_form_reasoning_is_not_guessed_or_silently_discarded():
    args = dict(ticker="GS", action="hold", number_of_stocks=0, **explanation())
    args.pop("alternatives_rejected")
    args["reasoning"] = "alternatives_rejected: BUY not justified"
    with pytest.raises(ValueError, match="alternatives_rejected"):
        ReviewDecisionResponse.model_validate(args)


@pytest.mark.parametrize("action,quantity", [("hold", 2), ("sell", 0), ("buy", "2")])
def test_flat_schema_still_rejects_invalid_trade_quantities(action, quantity):
    with pytest.raises(ValueError):
        ReviewDecisionResponse.model_validate(dict(ticker="GS", action=action,
                                                   number_of_stocks=quantity, **explanation()))


@pytest.mark.parametrize("action,quantity", [("sell", 3), ("hold", 0)])
def test_report_preserves_decision_reasons(monkeypatch, tmp_path, action, quantity):
    broker = SimpleNamespace(get_all_positions=lambda: [SimpleNamespace(symbol="AAPL")])
    monkeypatch.setattr(review, "get_client", lambda: broker)
    monkeypatch.setattr(review, "account_snapshot", lambda _: snapshot())
    monkeypatch.setattr(review, "_assess", lambda _: {"investment_case": "case"})
    decision = ExplainedDecision(ticker="AAPL", action=action, number_of_stocks=quantity,
                                 reasoning=explanation())
    monkeypatch.setattr(review, "debate_risk_decision", lambda *args: ({}, decision, snapshot(), 1))
    output = tmp_path / "review.json"
    report = review.review_queue([{"ticker": "AAPL"}], lambda c: c, output,
        lambda path, data: path.write_text(json.dumps(data)), tmp_path / "queue.json")
    entry = json.loads(output.read_text())["candidates"]["AAPL"]
    assert entry["decision_reasoning"] == explanation()
    assert entry["rationale"] == explanation()["rationale"]
    assert entry["action"] == ("sell" if action == "sell" else "pass")
    assert report["status"] == "complete"
