from langchain.tools import tool
import yfinance as yf

@tool
def get_key_metrics(ticker: str):
    """Get key metrics for a given stock ticker using yfinance."""
    stock = yf.Ticker(ticker)
    metrics = {
        "market_cap": stock.info.get("marketCap"),
        "pe_ratio": stock.info.get("trailingPE"),
        "forward_pe_ratio": stock.info.get("forwardPE"),
        "peg_ratio": stock.info.get("pegRatio"),
        "dividend_yield": stock.info.get("dividendYield"),
        "beta": stock.info.get("beta"),
    }
    return metrics

@tool
def compare_key_metrics(ticker1: str, ticker2: str):
    """Compare key metrics for two given stock tickers using yfinance. 
    Metrics1 is the stock we are considering, and metrics2 is the stock we are comparing against. 
    The result is the percentage change from metrics2 to metrics1."""
    metrics1 = get_key_metrics(ticker1)
    metrics2 = get_key_metrics(ticker2)

    # Compare metrics by taking metric1-metric2 and dividing by metric2
    # result = percentage change from metric2 to metric1
    # the stock we are considering is metrics1
    comparison = {
        "market_cap": (metrics1["market_cap"] - metrics2["market_cap"])/metrics2["market_cap"] * 100 if metrics2["market_cap"] else None,
        "pe_ratio": (metrics1["pe_ratio"] - metrics2["pe_ratio"])/metrics2["pe_ratio"] * 100 if metrics2["pe_ratio"] else None,
        "forward_pe_ratio": (metrics1["forward_pe_ratio"] - metrics2["forward_pe_ratio"])/metrics2["forward_pe_ratio"] * 100 if metrics2["forward_pe_ratio"] else None,
        "peg_ratio": (metrics1["peg_ratio"] - metrics2["peg_ratio"])/metrics2["peg_ratio"] * 100 if metrics2["peg_ratio"] else None,
        "dividend_yield": (metrics1["dividend_yield"] - metrics2["dividend_yield"])/metrics2["dividend_yield"] * 100 if metrics2["dividend_yield"] else None,
        "beta": (metrics1["beta"] - metrics2["beta"])/metrics2["beta"] * 100 if metrics2["beta"] else None
    }

    return comparison