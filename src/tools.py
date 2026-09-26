import os

import requests
from agents import function_tool
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("ALPHA_VANTAGE_API_KEY")


@function_tool
def data_for_one_day(symbol: str, date: str):
    """This tool finds 5 key data for a specific stock, 1. open, 2. high, 3. low, 4. close, 5. volume, on a specific date in a yyyy-mm-dd format.

    Args:
        symbol: stock ticker.
        dato: date for the key data in yyyy-mm-dd format.
    """
    if not api_key:
        raise ValueError("ALPHA_VANTAGE_API_KEY is not set")

    response = requests.get(
        "https://www.alphavantage.co/query",
        params={"function": "TIME_SERIES_DAILY", "symbol": symbol, "apikey": api_key},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    if "Time Series (Daily)" not in data:
        message = data.get("Error Message") or data.get("Note") or data.get("Information")
        raise ValueError(f"Alpha Vantage returned no daily data: {message or data}")
    try:
        return data["Time Series (Daily)"][date]
    except KeyError:
        raise ValueError(f"No trading data for {symbol} on {date}") from None
