import os
from functools import lru_cache

from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.trading.client import TradingClient


load_dotenv()


def _get_keys() -> tuple[str, str]:
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")

    if not api_key:
        raise RuntimeError(
            "ALPACA_API_KEY is missing. Add it to your .env file."
        )

    if not secret_key:
        raise RuntimeError(
            "ALPACA_SECRET_KEY is missing. Add it to your .env file."
        )

    return api_key, secret_key


@lru_cache(maxsize=1)
def get_trading_client() -> TradingClient:
    """
    Returns a cached Alpaca TradingClient configured for paper trading.
    """

    api_key, secret_key = _get_keys()

    return TradingClient(
        api_key=api_key,
        secret_key=secret_key,
        paper=True,
    )


@lru_cache(maxsize=1)
def get_data_client() -> StockHistoricalDataClient:
    """
    Returns a cached Alpaca market data client for stock prices.
    """

    api_key, secret_key = _get_keys()

    return StockHistoricalDataClient(api_key=api_key, secret_key=secret_key)