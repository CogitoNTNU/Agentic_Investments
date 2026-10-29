"""Finance analysis tool for a supervisor agent."""

import argparse
import json

from langchain_core.tools import tool

# Large intermediate data the caller does not need.
EXCLUDED_KEYS = {"messages", "statements", "peer_data"}


@tool
def finance_agent(ticker: str, peers: list[str] | None = None) -> dict:
    """Analyze the yfinance financial data and valuation of a ticker (e.g. AAPL).

    Compares the company with peers in the same S&P 500 sub-industry, or with
    the given peers. Returns the selected features, the peer comparison and a
    financial score from 0 to 10.
    """
    # Registering the tool should not initialize the LLM.
    from src.finance.graph import graph

    state = {"ticker": ticker, "messages": []}
    if peers:
        state["peers"] = peers
    result = graph.invoke(state, config={"recursion_limit": 30})
    return {key: value for key, value in result.items() if key not in EXCLUDED_KEYS}


def main():
    parser = argparse.ArgumentParser(description="Analyze the financial data of a ticker.")
    parser.add_argument("ticker")
    parser.add_argument("--peers", nargs="+", help="Peer tickers to compare with.")
    args = parser.parse_args()
    print(
        json.dumps(
            finance_agent.invoke({"ticker": args.ticker, "peers": args.peers}),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
