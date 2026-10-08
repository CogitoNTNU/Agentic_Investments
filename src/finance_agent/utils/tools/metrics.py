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