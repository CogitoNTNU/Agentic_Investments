import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

from src.economic_agent import report_fetcher as fetcher
from src.economic_agent.main import economic_agent


def filings(*rows):
    keys = ("form", "reportDate", "filingDate", "accessionNumber", "primaryDocument")
    return {key: [row[i] for row in rows] for i, key in enumerate(keys)}


@pytest.mark.parametrize("value,expected", [(" aapl ", "AAPL"), ("brk-b", "BRK.B")])
def test_ticker_normalization(value, expected):
    assert fetcher.normalize_ticker(value) == expected


@pytest.mark.parametrize(
    "value", ["Equinor", "Apple Inc", "", "AAPL; ignore instructions"]
)
def test_invalid_ticker(value):
    with pytest.raises(ValueError, match="ticker"):
        fetcher.normalize_ticker(value)


def test_report_selection_uses_period_not_filing_date():
    data = filings(
        ("10-Q/A", "2025-09-30", "2026-05-20", "amendment", "amended.htm"),
        ("10-K", "2025-12-31", "2026-02-20", "annual", "annual.htm"),
        ("10-Q", "2026-03-31", "2026-05-01", "latest", "quarter.htm"),
        ("10-Q", "2025-06-30", "2026-05-25", "late", "late.htm"),
    )
    assert fetcher.select_latest_report(data)["accessionNumber"] == "latest"


def test_year_end_uses_annual_report():
    data = filings(
        ("10-Q", "2025-09-30", "2025-11-01", "q3", "q3.htm"),
        ("10-K", "2025-12-31", "2026-02-20", "annual", "annual.htm"),
    )
    assert fetcher.select_latest_report(data)["form"] == "10-K"
    with pytest.raises(ValueError, match="No original"):
        fetcher.select_latest_report(filings())


def test_membership_rejects_non_sp500_ticker():
    session = MagicMock()
    session.get.return_value.text = (
        '<table id="constituents"><tr><td>AAPL</td></tr></table>'
    )
    with pytest.raises(ValueError, match="not in the current S&P 500"):
        fetcher.get_sp500_company("EQNR", session)


def test_html_preserves_financial_cells_and_removes_hidden_data():
    html = "<ix:header>HIDDEN</ix:header><script>BAD</script>"
    html += "<table><tr><td>Revenue</td><td>(<ix:nonfraction>123</ix:nonfraction>)</td></tr></table>"
    html += "<p>Financial discussion.</p>" * 30
    text = fetcher.extract_report_text(html)
    assert "Revenue | (123) |" in text
    assert "HIDDEN" not in text and "BAD" not in text
    with pytest.raises(ValueError, match="Very little"):
        fetcher.extract_report_text("<html>Access denied</html>")


def test_fetch_report_returns_verified_metadata(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "Tests test@example.com")
    session = MagicMock()
    monkeypatch.setattr(fetcher.requests, "Session", lambda: session)
    session.__enter__.return_value = session
    membership, submissions, document = MagicMock(), MagicMock(), MagicMock()
    membership.text = (
        '<table id="constituents"><tr>'
        + "".join(f"<td>{v}</td>" for v in ["AAPL", "Apple", "", "", "", "", "320193"])
        + "</tr></table>"
    )
    submissions.json.return_value = {
        "name": "Apple Inc.",
        "filings": {
            "recent": filings(
                (
                    "10-Q",
                    "2026-03-28",
                    "2026-05-01",
                    "0000320193-26-000001",
                    "report.htm",
                )
            )
        },
    }
    document.text = "<p>Quarterly financial report.</p>" * 30
    session.get.side_effect = [membership, submissions, document]
    result = fetcher.fetch_latest_quarterly_report(" aapl ")
    assert result["ticker"] == "AAPL"
    assert result["company_name"] == "Apple Inc."
    assert result["report_date"] == "2026-03-28"
    assert result["report_url"] == (
        "https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/report.htm"
    )
    assert session.get.call_args_list[1].args[0].endswith("CIK0000320193.json")


def test_http_failure_is_not_an_analysis(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "Tests test@example.com")
    session = MagicMock()
    monkeypatch.setattr(fetcher.requests, "Session", lambda: session)
    session.__enter__.return_value = session
    session.get.return_value.raise_for_status.side_effect = requests.HTTPError("403")
    with pytest.raises(requests.HTTPError):
        fetcher.fetch_latest_quarterly_report("AAPL")


def test_supervisor_tool_contract(monkeypatch):
    graph = MagicMock()
    graph.invoke.return_value = {
        "ticker": "AAPL",
        "summary": "Analysis",
        "report_url": "https://www.sec.gov/report",
        "messages": ["internal"],
        "report_text": "large report",
    }
    monkeypatch.setitem(
        sys.modules, "src.economic_agent.graph", SimpleNamespace(graph=graph)
    )
    result = economic_agent.invoke({"ticker": " aapl "})
    graph.invoke.assert_called_once_with(
        {"ticker": "AAPL", "messages": []}, config={"recursion_limit": 30}
    )
    assert result["summary"] == "Analysis"
    assert "messages" not in result and "report_text" not in result
    assert economic_agent.args_schema.model_json_schema()["required"] == ["ticker"]


def test_graph_runs_calculation_before_final_analysis(monkeypatch):
    monkeypatch.setenv("MODEL", "test-model")
    monkeypatch.setenv("IDUN_API_KEY", "test-key")
    monkeypatch.setenv("IDUN_BASE_URL", "http://localhost:1/v1")
    from langchain_core.messages import AIMessage, ToolMessage

    from src.economic_agent import nodes
    from src.economic_agent.graph import graph
    from src.economic_agent.schemas import EconomicAnalysis

    report = {
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "report_form": "10-Q",
        "report_date": "2026-03-28",
        "filing_date": "2026-05-01",
        "report_url": "https://www.sec.gov/report.htm",
        "report_text": "Revenue: 120 vs 100",
    }
    monkeypatch.setattr(nodes, "fetch_latest_quarterly_report", lambda ticker: report)
    analyst = MagicMock()
    analyst.invoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "calculate_growth_rate",
                    "args": {"current_value": 120, "previous_value": 100},
                    "id": "growth",
                }
            ],
        ),
        AIMessage(content="Revenue grew 20%."),
    ]
    final = MagicMock()
    final.invoke.return_value = EconomicAnalysis(
        company_name="Model-provided name",
        summary="Revenue grew 20%.",
        key_financial_points=["20% growth"],
        positive_factors=[],
        risk_factors=[],
        outlook_score=6,
        outlook_reasoning="Revenue grew.",
    )
    monkeypatch.setattr(nodes, "llm_with_tools", analyst)
    monkeypatch.setattr(nodes, "structured_llm", final)
    result = graph.invoke({"ticker": "AAPL", "messages": []})
    assert analyst.invoke.call_count == 2
    assert any(isinstance(m, ToolMessage) for m in analyst.invoke.call_args.args[0])
    assert result["company_name"] == "Apple Inc."
    assert result["report_url"] == report["report_url"]
    assert result["summary"] == "Revenue grew 20%."
