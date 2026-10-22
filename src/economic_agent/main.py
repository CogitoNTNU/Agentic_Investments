"""Economic analysis tool for a supervisor agent."""

import argparse
import json

from langchain_core.tools import tool

from src.economic_agent.report_fetcher import normalize_ticker


@tool
def economic_agent(ticker: str) -> dict:
    """Analyze the latest SEC financial report for an S&P 500 ticker (e.g. AAPL).

    Returns analysis, normalized ticker, report URL, form and dates.
    Uses a newer annual 10-K when available instead of an older quarterly 10-Q.
    """
    ticker = normalize_ticker(ticker)
    # Registering the tool should not initialize the LLM.
    from src.economic_agent.graph import graph

    result = graph.invoke(
        {"ticker": ticker, "messages": []}, config={"recursion_limit": 30}
    )
    return {
        key: value
        for key, value in result.items()
        if key not in {"messages", "report_text"}
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze an S&P 500 ticker.")
    parser.add_argument("ticker")
    args = parser.parse_args()
    print(json.dumps(economic_agent.invoke({"ticker": args.ticker}), indent=2))


if __name__ == "__main__":
    main()
