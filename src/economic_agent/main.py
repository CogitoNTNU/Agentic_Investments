"""Economic analysis tool for a supervisor agent."""

import argparse
import json

from langchain_core.tools import tool

from src.economic_agent.cache import load_analysis, save_analysis
from src.economic_agent.report_fetcher import get_latest_report, normalize_ticker


@tool
def economic_agent(ticker: str, force_refresh: bool = False) -> dict:
    """Analyze the latest SEC financial report for an S&P 500 ticker (e.g. AAPL).

    Returns analysis, normalized ticker, report URL, form and dates.
    Uses a newer annual 10-K when available instead of an older quarterly 10-Q.
    Reuses a saved analysis of the latest filing unless force_refresh is true.
    """
    ticker = normalize_ticker(ticker)
    report = get_latest_report(ticker)
    if not force_refresh:
        cached = load_analysis(report)
        if cached is not None:
            return cached
    # Registering the tool should not initialize the LLM.
    from src.economic_agent.graph import graph

    result = graph.invoke({**report, "messages": []}, config={"recursion_limit": 30})
    analysis = {
        key: value
        for key, value in result.items()
        if key not in {"messages", "report_text"}
    }
    return save_analysis(analysis)


def main():
    parser = argparse.ArgumentParser(description="Analyze an S&P 500 ticker.")
    parser.add_argument("ticker")
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            economic_agent.invoke(
                {"ticker": args.ticker, "force_refresh": args.force_refresh}
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
