from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from src.debate_agent import nodes
from src.debate_agent.schemas import Thesis, Rebuttal
from src.news_agent import news_agent as news


def thesis(count=5):
    return {
        "summary": "Research", "acknowledged_weaknesses": [], "missing_information": [],
        "arguments": [{"claim": f"Claim {i}", "rationale": "Reason",
                       "evidence_ids": ["finance"], "confidence": 0.5} for i in range(count)],
    }


def test_five_argument_model_response_survives_validation_and_gets_ids(monkeypatch):
    model = MagicMock()
    model.with_structured_output.return_value.invoke.return_value = thesis()
    monkeypatch.setattr(nodes, "get_model", lambda: model)
    result = nodes.bear_opening({"analysis_packet": {
        "ticker": "FDX", "evidence": [{"id": "finance"}],
    }})
    assert [a["argument_id"] for a in result["bear_analysis"]["arguments"]] == [
        "BEAR-1", "BEAR-2", "BEAR-3", "BEAR-4", "BEAR-5",
    ]
    assert model.with_structured_output.return_value.invoke.call_count == 1
    reply = {"responses": [{"opposing_argument_id": f"BEAR-{i}", "response": "Reply",
                            "evidence_ids": ["finance"]} for i in range(1, 6)],
             "revised_position": "Research", "conceded_points": [], "unresolved_questions": []}
    assert len(Rebuttal.model_validate(reply).responses) == 5


def test_debate_corrects_missing_or_invalid_structured_response(monkeypatch):
    model = MagicMock()
    invoke = model.with_structured_output.return_value.invoke
    invoke.side_effect = [None, {**thesis(), "arguments": []}, thesis(2)]
    monkeypatch.setattr(nodes, "get_model", lambda: model)
    assert len(nodes._invoke(Thesis, "System", {"ticker": "FDX"}).arguments) == 2
    assert invoke.call_count == 3


def test_debate_stops_retrying_invalid_responses(monkeypatch):
    model = MagicMock()
    invoke = model.with_structured_output.return_value.invoke
    invoke.return_value = None
    monkeypatch.setattr(nodes, "get_model", lambda: model)
    with pytest.raises(ValidationError):
        nodes._invoke(Thesis, "System", {})
    assert invoke.call_count == 3


def test_news_retries_none_and_reuses_fetched_evidence(monkeypatch):
    model = MagicMock()
    previous_messages = [{"role": "user", "content": "Ticker FDX"},
                         {"role": "assistant", "content": "Previously retrieved news"}]
    model.invoke.side_effect = [
        {"structured_response": None, "messages": previous_messages},
        {"structured_response": {"stock": {"ticker": "WRONG", "status": "ok", "period_days": 1}}},
    ]
    monkeypatch.setattr(news, "agent", model)
    result = news.run_news_agent("FDX", 7)
    assert result.stock.ticker == "FDX"
    assert result.stock.period_days == 7
    assert result.stock.status == "ok"
    assert model.invoke.call_count == 2
    assert model.invoke.call_args.args[0]["messages"][:2] == previous_messages


@pytest.mark.parametrize("bad_result", [{"structured_response": None}, {}, {"structured_response": {"stock": {}}}])
def test_news_returns_error_report_instead_of_attribute_error(monkeypatch, bad_result):
    model = MagicMock()
    model.invoke.return_value = bad_result
    monkeypatch.setattr(news, "agent", model)
    result = news.run_news_agent("FDX")
    assert result.stock.status == "error"
    assert result.stock.note
    assert result.stock.ticker == "FDX"
    assert model.invoke.call_count == 2
