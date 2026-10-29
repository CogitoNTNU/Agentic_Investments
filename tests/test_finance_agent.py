import json
import os

import pandas as pd
import pytest
import yfinance as yf
from dotenv import load_dotenv
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage, ToolMessage

# llm.py builds the client on import, which needs a key even when no LLM is called.
load_dotenv()
os.environ.setdefault("IDUN_API_KEY", "test-key")

from src.finance import nodes  # noqa: E402
from src.finance.features import compute_features  # noqa: E402
from src.finance.graph import graph  # noqa: E402
from src.finance.main import finance_agent  # noqa: E402
from src.finance.schemas import FeatureSelection, FinanceAnalysis  # noqa: E402

YEARS = ["2023-12-31", "2024-12-31", "2025-12-31"]
QUARTERS = ["2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"]


def statement(rows: dict[str, list[float]], periods: list[str]) -> pd.DataFrame:
    # yfinance layout: rows are line items, columns are period end dates.
    return pd.DataFrame(rows, index=pd.to_datetime(periods)).T


def bank(market_cap: float, pe_ratio: float, scale: float, margin: float) -> dict:
    """A bank-like company: no gross profit, operating income or current assets."""
    return {
        "info": {
            "longName": "Test Bank",
            "sector": "Financial Services",
            "industry": "Banks - Diversified",
            "financialCurrency": "USD",
            "marketCap": market_cap,
            "trailingPE": pe_ratio,
            "forwardPE": pe_ratio - 1,
            "pegRatio": 1.5,
            "dividendYield": 2.0,
            "beta": 1.0,
        },
        "income_stmt": statement(
            {
                "Total Revenue": [100 * scale, 110 * scale, 121 * scale],
                "Net Income": [20 * scale * margin, 22 * scale * margin, 30 * scale * margin],
            },
            YEARS,
        ),
        "balance_sheet": statement(
            {"Stockholders Equity": [200 * scale] * 3, "Total Debt": [100 * scale] * 3},
            YEARS,
        ),
        # No "Free Cash Flow" row, so it is derived from operating cash flow and capex.
        "cashflow": statement(
            {
                "Operating Cash Flow": [30 * scale, 30 * scale, 40 * scale],
                "Capital Expenditure": [-5 * scale, -5 * scale, -10 * scale],
            },
            YEARS,
        ),
        "quarterly_income_stmt": statement(
            {
                "Total Revenue": [25 * scale, 26 * scale, 27 * scale, 28 * scale, 30 * scale],
                "Net Income": [5 * scale, 5 * scale, 6 * scale, 6 * scale, 7.5 * scale],
            },
            QUARTERS,
        ),
        "quarterly_balance_sheet": statement(
            {"Stockholders Equity": [200 * scale] * 5}, QUARTERS
        ),
        "quarterly_cashflow": pd.DataFrame(),
    }


COMPANIES = {
    "JPM": bank(900e9, 15, scale=1.0, margin=1.0),
    "BAC": bank(360e9, 12, scale=0.5, margin=0.8),
    "WFC": bank(255e9, 13, scale=0.4, margin=0.9),
    "C": bank(210e9, 10, scale=0.3, margin=0.6),
    "USB": bank(94e9, 11, scale=0.2, margin=1.0),
    "PNC": bank(92e9, 11, scale=0.2, margin=1.0),
    "TFC": bank(60e9, 11, scale=0.1, margin=1.0),
}


class FakeTicker:
    def __init__(self, ticker: str):
        self.ticker = ticker
        company = COMPANIES.get(ticker)
        # Unknown tickers behave like yfinance: almost empty info and no statements.
        self.info = company["info"] if company else {"trailingPegRatio": None}
        self.fast_info = {"marketCap": self.info.get("marketCap")}
        for name in (
            "income_stmt",
            "balance_sheet",
            "cashflow",
            "quarterly_income_stmt",
            "quarterly_balance_sheet",
            "quarterly_cashflow",
        ):
            setattr(self, name, company[name] if company else pd.DataFrame())


class FakeLLM:
    """Returns the given responses in order and records the messages it received."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


ANALYSIS = FinanceAnalysis(
    summary="Profitable bank.",
    valuation_assessment="P/E above peers.",
    peer_comparison=["ROE above the peer median."],
    key_trends=["Revenue grows 10% a year."],
    positive_factors=["High ROE."],
    risk_factors=["Higher valuation than peers."],
    financial_score=7,
    score_reasoning="Strong profitability, higher valuation.",
)


@pytest.fixture
def fake_yfinance(monkeypatch):
    # data_fetcher, peers and tools all look up yf.Ticker when they are called.
    monkeypatch.setattr(yf, "Ticker", FakeTicker)


@pytest.fixture
def fake_llms(monkeypatch):
    selector = FakeLLM(
        FeatureSelection(
            # gross_margin has no value for a bank and must be dropped.
            features=["return_on_equity", "gross_margin", "net_margin"],
            reasoning="ROE and net margin matter for banks.",
        )
    )
    analyst = FakeLLM(
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "compare_key_metrics",
                    "args": {"ticker1": "JPM", "ticker2": "BAC"},
                    "id": "call-1",
                }
            ],
        ),
        AIMessage(content="JPM has a higher ROE than its peers."),
    )
    final = FakeLLM(ANALYSIS)
    monkeypatch.setattr(nodes, "feature_selector_llm", selector)
    monkeypatch.setattr(nodes, "llm_with_tools", analyst)
    monkeypatch.setattr(nodes, "structured_llm", final)
    return selector, analyst, final


def test_graph_runs_end_to_end(fake_yfinance, fake_llms):
    selector, analyst, final = fake_llms

    result = graph.invoke({"ticker": " jpm ", "messages": []})

    # fetch_data and compute_features
    assert result["ticker"] == "JPM"
    assert result["company_info"]["sector"] == "Financial Services"
    assert result["features_period"] == "2025-12-31"
    assert result["features"] == {
        "revenue_growth": 10.0,
        "gross_margin": None,
        "operating_margin": None,
        "net_margin": 24.79,
        "return_on_equity": 15.0,
        "debt_to_equity": 0.5,
        "current_ratio": None,
        "free_cash_flow": 30.0,
        "free_cash_flow_margin": 24.79,
        "earnings_growth": 36.36,
    }
    # Quarterly growth compares with the same quarter one year earlier.
    assert result["quarterly_feature_history"]["revenue_growth"] == {"2026-06-30": 20.0}

    # select_features drops the feature without a value.
    assert result["selected_features"] == ["return_on_equity", "net_margin"]
    assert result["feature_reasoning"] == "ROE and net margin matter for banks."

    # fetch_peers picks the three closest in market cap from the same sub-industry.
    assert result["peers"] == ["BAC", "WFC", "C"]
    comparison = result["peer_comparison_data"]
    assert comparison["key_metrics"]["pe_ratio"] == {
        "company": 15,
        "peer_median": 12,
        "difference": 25.0,
    }
    assert comparison["features"]["return_on_equity"] == {
        "company": 15.0,
        "peer_median": 12.0,
        "difference": 3.0,
    }

    # analyst ⇄ tools: the tool call ran against the fake yfinance data.
    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert json.loads(tool_messages[0].content)["pe_ratio"] == 25.0
    assert len(analyst.calls) == 2

    # The analyst gets the computed features, not the raw statements.
    prompt = analyst.calls[0][-1].content
    assert '"return_on_equity"' in prompt and "BAC" in prompt
    assert "Total Revenue" not in prompt

    # final_analysis
    assert len(final.calls) == 1
    assert result["financial_score"] == 7
    assert result["summary"] == "Profitable bank."


def test_tool_uses_given_peers_and_hides_internal_data(fake_yfinance, fake_llms):
    result = finance_agent.invoke({"ticker": "JPM", "peers": ["bac", "JPM", "brk.b"]})

    # The company itself is removed, and BRK-B has no data, so it is skipped.
    assert result["peers"] == ["BAC"]
    assert result["financial_score"] == 7
    assert not {"messages", "statements", "peer_data"} & set(result)


def test_unknown_ticker_raises(fake_yfinance, fake_llms):
    with pytest.raises(ValueError, match="No yfinance data"):
        graph.invoke({"ticker": "ZZZZ", "messages": []})


@pytest.mark.parametrize(
    "response",
    [
        OutputParserException("bad output"),
        FeatureSelection(features=["gross_margin"], reasoning="Not available."),
    ],
)
def test_selection_falls_back_to_sector_defaults(monkeypatch, response):
    monkeypatch.setattr(nodes, "feature_selector_llm", FakeLLM(response))
    state = {
        "company_info": {"company_name": "Test Bank", "sector": "Financial Services", "industry": "Banks"},
        "features_period": "2025-12-31",
        "features": {"return_on_equity": 15.0, "net_margin": 24.79, "gross_margin": None},
    }

    result = nodes.select_features_node(state)

    assert result["selected_features"] == ["return_on_equity", "net_margin"]
    assert result["feature_reasoning"] == "Default features for the Financial Services sector."


def test_features_skip_misleading_and_stale_values():
    statements = {
        "income": {
            "Total Revenue": {"2024-12-31": 100.0, "2025-12-31": 120.0},
            "Net Income": {"2024-12-31": 10.0, "2025-12-31": 12.0},
            # Only reported for the older year.
            "Gross Profit": {"2024-12-31": 40.0},
        },
        "balance_sheet": {
            "Stockholders Equity": {"2025-12-31": -50.0},
            "Total Debt": {"2025-12-31": 80.0},
        },
        "cashflow": {"Free Cash Flow": {"2025-12-31": 18.0}},
    }

    result = compute_features(statements)

    features = result["features"]
    assert features["net_margin"] == 10.0
    assert features["free_cash_flow_margin"] == 15.0
    # Negative equity gives no ROE or debt-to-equity.
    assert features["return_on_equity"] is None
    assert features["debt_to_equity"] is None
    # An older value is never presented as the current one.
    assert features["gross_margin"] is None
    assert result["feature_history"]["gross_margin"] == {"2024-12-31": 40.0}


@pytest.mark.skipif(
    not os.getenv("RUN_LIVE_TESTS"),
    reason="Calls yfinance and the IDUN LLM; set RUN_LIVE_TESTS=1 to run.",
)
def test_live_finance_agent():
    result = finance_agent.invoke({"ticker": "JPM"})

    assert result["ticker"] == "JPM"
    assert result["selected_features"]
    assert result["peers"]
    assert 0 <= result["financial_score"] <= 10
