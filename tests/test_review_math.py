import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.decision_agent import agent, review
from src.decision_agent.review_math import portfolio_facts, position_scenario, sizing_examples
from src.decision_agent.review_policy import EVIDENCE_POLICY
from src.decision_agent.schemas import Decision


def account():
    return dict(positions={"RJF": "25", "OTHER": "1"}, current_number_of_stocks=25,
                cash="12698.21", available_cash="9759.89", buying_power="280000",
                replacement_reserved_cash="0", open_orders=[
                    dict(id="regn", symbol="REGN", side="buy", qty="2", filled_qty="0", limit_price="949.8"),
                    dict(id="ppg", symbol="PPG", side="buy", qty="8", filled_qty="0", limit_price="129.84")],
                market_context=dict(estimated_equity="99145", prices={"RJF": "168.67", "OTHER": "1000"},
                    holdings={"RJF": {"weight_pct": "4.253"}, "OTHER": {"weight_pct": "1.009"}}))


def test_rjf_reservations_are_not_subtracted_twice():
    snapshot = account()
    facts = portfolio_facts(snapshot)
    assert facts["available_cash_after_all_reservations"] == "9759.89"
    assert facts["cash_unavailable_for_new_buys"] == "2938.32"
    scenario = position_scenario("RJF", snapshot, "buy", 10)
    assert scenario["buffered_buy_cost"] == "1720.40"
    assert scenario["available_cash_after_buy_reservation"] == "8039.49"
    assert scenario["cash_fundable_now"]
    assert scenario["projected_shares_after_full_fill"] == "35"


def test_local_reserves_and_broker_power_are_respected_without_recounting():
    snapshot = account()
    snapshot.update(available_cash="1000", replacement_reserved_cash="8759.89", buying_power="800")
    scenario = position_scenario("RJF", snapshot, "buy", 10)
    assert not scenario["cash_fundable_now"]
    assert scenario["cash_shortfall"] == "920.40"
    assert portfolio_facts(snapshot)["available_cash_after_all_reservations"] == "1000"


def test_counts_include_owned_positions_not_pending_orders_or_zero_positions():
    snapshot = account()
    snapshot["positions"] = {f"T{i}": "1" for i in range(32)} | {"ZERO": "0"}
    assert portfolio_facts(snapshot)["position_count"] == 32


def test_downside_is_portfolio_percentage_points_not_predicted_probability():
    snapshot = account()
    snapshot["positions"]["RJF"] = "4"
    snapshot["market_context"].update(estimated_equity="100000", prices={"RJF": "1000"})
    scenario = position_scenario("RJF", snapshot, "buy", 2)
    assert Decimal(scenario["weight_before_pct"]) == 4
    assert Decimal(scenario["weight_after_pct"]) == 6
    assert Decimal(scenario["stress_loss_pct_of_current_equity"]["40"]["before"]) == Decimal("1.6")
    assert Decimal(scenario["stress_loss_pct_of_current_equity"]["40"]["after"]) == Decimal("2.4")
    assert "not forecasts" in scenario["assumptions"]


def test_full_exit_does_not_credit_unfilled_sale_proceeds():
    snapshot = account()
    scenario = position_scenario("RJF", snapshot, "sell", 25)
    assert Decimal(scenario["weight_after_pct"]) == 0
    assert scenario["available_cash_after_buy_reservation"] == "9759.89"
    assert snapshot["positions"]["RJF"] == "25"


@pytest.mark.parametrize("action,qty", [("sell", 26), ("buy", 0), ("hold", 1), ("buy", True), ("buy", -1)])
def test_invalid_scenarios_fail(action, qty):
    with pytest.raises(ValueError):
        position_scenario("RJF", account(), action, qty)


def test_sizing_examples_include_trim_and_exit_not_only_buy():
    options = sizing_examples("RJF", account())
    assert {(o["action"], o["shares_to_trade"]) for o in options} >= {
        ("hold", 0), ("buy", 2), ("sell", 6), ("sell", 12), ("sell", 25)}


def test_examples_exclude_shares_already_committed_to_sale():
    snapshot = account()
    snapshot["open_orders"].append(dict(symbol="RJF", side="sell", qty="24", filled_qty="1"))
    sells = [s for s in sizing_examples("RJF", snapshot) if s["action"] == "sell"]
    assert [s["shares_to_trade"] for s in sells] == [2]


def test_model_receives_authoritative_math_and_shared_policy(monkeypatch):
    model = MagicMock()
    model.with_structured_output.return_value.invoke.return_value = dict(
        ticker="RJF", action="hold", number_of_stocks=0, rationale="Keep current exposure.",
        decisive_evidence=["report"], alternatives_rejected="Trim evaluated.",
        sizing_rationale="Downside is acceptable for the stated case.",
        risks_and_uncertainties="Costs unknown.", change_conditions="Changed earnings outlook.")
    monkeypatch.setattr(agent, "get_model", lambda: model)
    agent.recommend_decision({}, "RJF", 25, account(), review_rotation=True)
    messages = model.with_structured_output.return_value.invoke.call_args.args[0]
    assert EVIDENCE_POLICY in messages[0][1]
    payload = json.loads(messages[1][1])
    assert payload["portfolio_facts"] == portfolio_facts(account())
    assert payload["sizing_examples"] == sizing_examples("RJF", account())


def test_comparison_receives_identical_cash_rules_and_desired_size_math(monkeypatch):
    ask = MagicMock(return_value=review.ReviewDecision(action="pass", rationale="No edge", rotation=None))
    monkeypatch.setattr(review, "_ask", ask)
    review.compare_candidate("RJF", {"decision": {"number_of_stocks": 10}, "max_cash_buy_shares": 50},
                             {"RJF": {}, "OTHER": {}}, account())
    _, prompt, payload = ask.call_args.args
    assert EVIDENCE_POLICY in prompt
    assert payload["portfolio_facts"] == portfolio_facts(account())
    assert payload["decision_math"]["available_cash_after_buy_reservation"] == "8039.49"


def test_report_distinguishes_proposed_and_capped_buy_sizes(monkeypatch, tmp_path):
    snapshot = account()
    broker = SimpleNamespace(get_all_positions=lambda: [SimpleNamespace(symbol=s) for s in snapshot["positions"]])
    monkeypatch.setattr(review, "get_client", lambda: broker)
    monkeypatch.setattr(review, "account_snapshot", lambda _: snapshot)
    monkeypatch.setattr(review, "_assess", lambda _: {})
    monkeypatch.setattr(review, "debate_risk_decision", lambda *args: (
        {}, Decision(ticker="RJF", action="buy", number_of_stocks=10), snapshot, 3))
    monkeypatch.setattr(review, "compare_candidate", lambda *args: review.ReviewDecision(
        action="buy_with_cash", cash_buy_shares=10, rotation=None, rationale="Measured add"))
    output = tmp_path / "report.json"
    review.review_queue([{"ticker": "RJF"}], lambda c: c, output,
                        lambda path, data: path.write_text(json.dumps(data)), tmp_path / "queue.json")
    entry = json.loads(output.read_text())["candidates"]["RJF"]
    assert entry["risk_decision_math"]["shares_to_trade"] == 10
    assert entry["planned_trade_math"]["buy"]["shares_to_trade"] == 3
    assert entry["planned_trade_math"]["buy"]["projected_shares_after_full_fill"] == "28"
