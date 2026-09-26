from datetime import UTC, datetime

from agents import Agent, ModelSettings

# Imports from other files here
from model import get_model
from tools import *

today: str = datetime.now(tz=UTC).date().isoformat()

stock_agent = Agent(
    name="Stock Research Agent",
    model=get_model(),
    model_settings=ModelSettings(extra_body={"reasoning_effort": "low"}),
    instructions=f"""
    You are an equity research agent.

    Your job is to analyze publicly traded companies.

    Use the available tools to obtain factual market data.

    Consider:
    - market data
    - company fundamentals
    - recent news
    - catalysts
    - risks

    Separate facts from interpretation.

    Never invent financial data.

    If reliable information is unavailable,
    return INSUFFICIENT_DATA.

    Produce a structured investment research recommendation. Today is {today}.
    If market-data retrieval fails, report the exact tool error and do not fill the gap with unverified claims.
    """,
    tools=[
        data_for_one_day,
        news,
        insider_transactions,
        congress_trades,
        politician_metadata,
        company_overview,
    ],
    # output_type =
)
