import os

import requests
from agents import function_tool
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("ALPHA_VANTAGE_API_KEY")


@function_tool
def data_for_one_day(symbol: str, dato: str):
    """This tool finds 5 key data for a specific stock, 1. open, 2. high, 3. low, 4. close, 5. volume, on a specific date in a yyyy-mm-dd format.

    Args:
        symbol: stock ticker.
        dato: date for the key data in yyyy-mm-dd format.
    """
    response = requests.get(
        "https://www.alphavantage.co/query",
        params={"function": "TIME_SERIES_DAILY", "symbol": symbol, "apikey": api_key},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    return data["Time Series (Daily)"][dato]
