from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID
from typing import Any

from alpaca.common.exceptions import APIError


def to_jsonable(value: Any) -> Any:
    """
    Converts Alpaca SDK models and other Python objects into
    JSON-friendly Python values.
    """

    if value is None:
        return None

    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")

    if isinstance(value, dict):
        return {
            str(key): to_jsonable(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, UUID):
        return str(value)

    return value


def success(**kwargs) -> dict:
    """
    Standard success response returned by Alpaca tools.
    """

    return {
        "ok": True,
        **{
            key: to_jsonable(value)
            for key, value in kwargs.items()
        },
    }


def api_error(exc: APIError) -> dict:
    """
    Converts Alpaca API exceptions into agent-friendly output.
    """

    return {
        "ok": False,
        "error": str(exc),
    }


def normalize_symbol(symbol: str) -> str:
    """
    Normalizes a stock ticker.
    """

    if not symbol or not symbol.strip():
        raise ValueError("Symbol cannot be empty.")

    return symbol.strip().upper()