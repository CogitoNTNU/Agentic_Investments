import os

import requests
from agents import function_tool
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("ALPHA_VANTAGE_API_KEY")


# @function_tool
# def data_for_one_day(symbol: str, date: str):
#     """This tool finds 5 key data for a specific stock, 1. open, 2. high, 3. low, 4. close, 5. volume, on a specific date in a yyyy-mm-dd format.

#     Args:
#         symbol: stock ticker.
#         date: date for the key data in yyyy-mm-dd format.
#     """
#     if not api_key:
#         raise ValueError("ALPHA_VANTAGE_API_KEY is not set")

#     response = requests.get(
#         "https://www.alphavantage.co/query",
#         params={"function": "TIME_SERIES_DAILY", "symbol": symbol, "apikey": api_key},
#         timeout=10,
#     )
#     response.raise_for_status()
#     data = response.json()
#     if "Time Series (Daily)" not in data:
#         message = (
#             data.get("Error Message") or data.get("Note") or data.get("Information")
#         )
#         raise ValueError(f"Alpha Vantage returned no daily data: {message or data}")
#     try:
#         return data["Time Series (Daily)"][date]
#     except KeyError:
#         raise ValueError(f"No trading data for {symbol} on {date}") from None


# @function_tool
# def news(ticker: str):
#     """
#     This tool finds the latest news for a specific stock.
#     Args:
#          symbol: stock ticker.
#     """
#     if not api_key:
#         raise ValueError("ALPHA_VANTAGE_API_KEY is not set")

#     response = requests.get(
#         "https://www.alphavantage.co/query",
#         params={"function": "NEWS_SENTIMENT", "tickers": ticker, "apikey": api_key},
#         timeout=10,
#     )
#     response.raise_for_status()
#     data = response.json()
#     if "feed" not in data:
#         message = (
#             data.get("Error Message") or data.get("Note") or data.get("Information")
#         )
#         raise ValueError(f"Alpha Vantage returned no news data: {message or data}")
#     return data["feed"]


# @function_tool
# def insider_transactions(symbol: str, from_date: str | None = None):
#     """
#     This tool finds the latest and historical insider transactions for a stock.
#     Args:
#         symbol: stock ticker.
#         from_date: optional start date in yyyy-mm-dd format.
#     """
#     if not api_key:
#         raise ValueError("ALPHA_VANTAGE_API_KEY is not set")

#     response = requests.get(
#         "https://www.alphavantage.co/query",
#         params={
#             "function": "INSIDER_TRANSACTIONS",
#             "symbol": symbol,
#             "apikey": api_key,
#             **({"from": from_date} if from_date else {}),
#         },
#         timeout=10,
#     )
#     response.raise_for_status()
#     data = response.json()
#     if "data" not in data:
#         message = (
#             data.get("Error Message") or data.get("Note") or data.get("Information")
#         )
#         raise ValueError(
#             f"Alpha Vantage returned no insider transaction data: {message or data}"
#         )
#     return data["data"]


# @function_tool
# def congress_trades(
#     symbol: str | None = None,
#     bioguide_id: str | None = None,
#     from_date: str | None = None,
# ):
#     """
#     This tool finds the latest and historical congress transactions for a stock.
#     Args:
#         symbol: stock ticker.
#         from_date: optional start date in yyyy-mm-dd format.
#     """
#     if not api_key:
#         raise ValueError("ALPHA_VANTAGE_API_KEY is not set")

#     if bool(symbol) == bool(bioguide_id):
#         raise ValueError("Provide exactly one of symbol or bioguide_id")

#     response = requests.get(
#         "https://www.alphavantage.co/query",
#         params={
#             "function": "CONGRESS_TRADES",
#             **({"symbol": symbol} if symbol else {"bioguide_id": bioguide_id}),
#             "apikey": api_key,
#             **({"from": from_date} if from_date else {}),
#         },
#         timeout=10,
#     )
#     response.raise_for_status()
#     data = response.json()
#     if "data" not in data:
#         message = (
#             data.get("Error Message") or data.get("Note") or data.get("Information")
#         )
#         raise ValueError(
#             f"Alpha Vantage returned no congress transaction data: {message or data}"
#         )
#     return data["data"]


# @function_tool
# def politician_metadata():
#     """
#     This tool finds key metadata for US congressional representatives.
#     """
#     if not api_key:
#         raise ValueError("ALPHA_VANTAGE_API_KEY is not set")

#     response = requests.get(
#         "https://www.alphavantage.co/query",
#         params={
#             "function": "POLITICIAN_METADATA",
#             "apikey": api_key,
#         },
#         timeout=10,
#     )
#     response.raise_for_status()
#     data = response.json()
#     if "data" not in data:
#         message = (
#             data.get("Error Message") or data.get("Note") or data.get("Information")
#         )
#         raise ValueError(
#             f"Alpha Vantage returned no politician metadata: {message or data}"
#         )
#     return data["data"]


# @function_tool
# def company_overview(symbol: str):
#     """
#     This tool finds company information, financial ratios, and other key metrics
#     for a stock.
#     Args:
#         symbol: stock ticker.
#     """
#     if not api_key:
#         raise ValueError("ALPHA_VANTAGE_API_KEY is not set")

#     response = requests.get(
#         "https://www.alphavantage.co/query",
#         params={
#             "function": "OVERVIEW",
#             "symbol": symbol,
#             "apikey": api_key,
#         },
#         timeout=10,
#     )
#     response.raise_for_status()
#     data = response.json()
#     if not data or "Symbol" not in data:
#         message = (
#             data.get("Error Message") or data.get("Note") or data.get("Information")
#         )
#         raise ValueError(
#             f"Alpha Vantage returned no company overview data: {message or data}"
#         )
#     return data

