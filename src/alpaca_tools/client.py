import os
from functools import lru_cache

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient


load_dotenv()


@lru_cache(maxsize=1)
def get_trading_client() -> TradingClient:
    """
    Returns a cached Alpaca TradingClient configured for paper trading.
    """

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

    return TradingClient(
        api_key=api_key,
        secret_key=secret_key,
        paper=True,
    )