"""Runs the news, economic and finance agents in parallel for the supervisor."""

import json
from typing import Any

from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from src.economic_agent.main import economic_agent
from src.finance.main import finance_agent
from src.news_agent.news_agent import get_stock_news_report


class ResearchState(TypedDict, total=False):
    ticker: str
    days: int
    news_agent: Any
    economic_agent: Any
    finance_agent: Any


def _error(error: Exception) -> dict:
    # One failing agent must not stop the other branches.
    return {"status": "error", "note": f"{type(error).__name__}: {error}"}


def news_node(state: ResearchState) -> dict:
    try:
        report = get_stock_news_report.invoke(
            {"ticker": state["ticker"], "days": state.get("days", 7)}
        )
        return {"news_agent": json.loads(report)}
    except Exception as error:
        return {"news_agent": _error(error)}


def economic_node(state: ResearchState) -> dict:
    try:
        return {"economic_agent": economic_agent.invoke({"ticker": state["ticker"]})}
    except Exception as error:
        return {"economic_agent": _error(error)}


def finance_node(state: ResearchState) -> dict:
    try:
        return {"finance_agent": finance_agent.invoke({"ticker": state["ticker"]})}
    except Exception as error:
        return {"finance_agent": _error(error)}


builder = StateGraph(ResearchState)
builder.add_node("news", news_node)
builder.add_node("economic", economic_node)
builder.add_node("finance", finance_node)
for node in ("news", "economic", "finance"):
    builder.add_edge(START, node)
    builder.add_edge(node, END)
research_graph = builder.compile(name="research_graph")


@tool
def gather_research_data(ticker: str, days: int = 7) -> str:
    """Run news_agent, economic_agent and finance_agent in parallel for one ticker.

    Returns JSON with one key per agent. A failed agent has status "error"
    and the reason in "note".

    Args:
        ticker: Stock ticker, e.g. 'AAPL'.
        days: News period in days (default 7, max 30).
    """
    result = research_graph.invoke({"ticker": ticker.strip().upper(), "days": days})
    return json.dumps(result, ensure_ascii=False, default=str)
