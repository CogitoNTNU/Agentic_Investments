"""Tools the analyst LLM can call during the analysis."""

import yfinance as yf
from langchain_core.tools import tool

from src.finance.data_fetcher import KEY_METRICS, fetch_key_metrics, normalize_ticker


def percentage_change(value: float | None, reference: float | None) -> float | None:
    if value is None or not reference:
        return None
    return (value - reference) / reference * 100


@tool
def compare_key_metrics(ticker1: str, ticker2: str) -> dict:
    """Compare key metrics for two given stock tickers using yfinance.
    Metrics1 is the stock we are considering, and metrics2 is the stock we are comparing against.
    The result is the percentage change from metrics2 to metrics1."""
    metrics1 = fetch_key_metrics(yf.Ticker(normalize_ticker(ticker1)))
    metrics2 = fetch_key_metrics(yf.Ticker(normalize_ticker(ticker2)))
    return {
        name: percentage_change(metrics1[name], metrics2[name])
        for name in KEY_METRICS
    }


FINANCE_TOOLS = [
    compare_key_metrics,
]
