import json
import sys
from types import SimpleNamespace

import pytest

from src import main
from src.decision_agent import trading


def save_candidates(directory, name, tickers):
    (directory / name).write_text(json.dumps({
        "candidates": [{"ticker": ticker} for ticker in tickers]
    }))


def test_grouped_preferred_and_duplicate_tickers_removed(tmp_path):
    save_candidates(tmp_path, "grouped_candidates.json", [" aapl ", "MSFT", "AAPL"])
    save_candidates(tmp_path, "latest_candidates.json", ["NVDA"])
    assert [c["ticker"] for c in main.load_candidates(tmp_path)] == ["AAPL", "MSFT"]


def test_latest_fallback_and_empty_queue(tmp_path):
    save_candidates(tmp_path, "latest_candidates.json", ["NVDA"])
    assert main.load_candidates(tmp_path)[0]["ticker"] == "NVDA"
    save_candidates(tmp_path, "latest_candidates.json", [])
    assert not main.load_candidates(tmp_path)


def test_queue_finishes_each_candidate_before_starting_next(monkeypatch, tmp_path):
    save_candidates(tmp_path, "grouped_candidates.json", ["AAPL", "MSFT"])
    queue = main.load_candidates(tmp_path)
    monkeypatch.setattr(main, "load_candidates", lambda: queue)
    events = []
    monkeypatch.setattr(trading, "sync_pending_order", lambda: events.append("sync"))

    def process(candidate):
        ticker = candidate["ticker"]
        events.extend([f"research:{ticker}", f"decision:{ticker}"])
        return {"decision": {"ticker": ticker, "action": "hold", "number_of_stocks": 0}}

    monkeypatch.setattr(main, "process_candidate", process)
    main.main()
    assert events == ["sync", "research:AAPL", "decision:AAPL", "research:MSFT", "decision:MSFT"]
    assert not queue


def test_failure_retains_current_candidate_and_stops_queue(monkeypatch, tmp_path):
    save_candidates(tmp_path, "latest_candidates.json", ["AAPL", "MSFT"])
    queue = main.load_candidates(tmp_path)
    monkeypatch.setattr(main, "load_candidates", lambda: queue)
    monkeypatch.setattr(trading, "sync_pending_order", lambda: None)

    def fail(candidate):
        raise TimeoutError("pending order")

    monkeypatch.setattr(main, "process_candidate", fail)
    with pytest.raises(TimeoutError, match="pending"):
        main.main()
    assert [c["ticker"] for c in queue] == ["AAPL", "MSFT"]


def test_candidate_passes_complete_research_and_discovery_to_debate(monkeypatch):
    from src.debate_agent.graph import graph
    from src.debate_agent.schemas import AnalysisPacket

    research = {"ticker": "AAPL", "news_agent": {"status": "error"},
                "economic_agent": {"summary": "Report"}, "finance_agent": "Metrics"}
    calls = []

    def gather(payload):
        calls.append(payload)
        return json.dumps(research)

    monkeypatch.setitem(sys.modules, "src.supervisor.research", SimpleNamespace(
        gather_research_data=SimpleNamespace(invoke=gather)
    ))

    def debate(state):
        packet = AnalysisPacket.model_validate(state["analysis_packet"])
        assert state["ticker"] == packet.ticker == "AAPL"
        evidence = {e.source: json.loads(e.statement) for e in packet.evidence}
        assert evidence["discovery"]["summary"] == "Discovery event"
        for source in ("news_agent", "economic_agent", "finance_agent"):
            assert evidence[source] == research[source]
        return {**state, "decision": {"ticker": "AAPL", "action": "hold", "number_of_stocks": 0}}

    monkeypatch.setattr(graph, "invoke", debate)
    result = main.process_candidate({"ticker": "AAPL", "summary": "Discovery event"})
    assert result["decision"]["action"] == "hold"
    assert calls == [{"ticker": "AAPL"}]
