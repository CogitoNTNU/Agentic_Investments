import json
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from .schemas import Decision

PORTFOLIO_PATH = Path(__file__).resolve().parents[2] / "portfolio.json"
_lock = RLock()


class Position(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1)
    number_of_stocks: int = Field(strict=True, gt=0)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("ticker must not be blank")
        return value


def read_portfolio() -> list[dict]:
    """A missing file means an empty portfolio; malformed files raise errors."""
    with _lock:
        if not PORTFOLIO_PATH.exists():
            return []
        positions = TypeAdapter(list[Position]).validate_json(
            PORTFOLIO_PATH.read_text(encoding="utf-8")
        )
        if len({p.ticker for p in positions}) != len(positions):
            raise ValueError("Portfolio contains duplicate tickers")
        return [position.model_dump() for position in positions]


def get_number_of_stocks(ticker: str) -> int:
    ticker = ticker.strip().upper()
    return next(
        (p["number_of_stocks"] for p in read_portfolio() if p["ticker"] == ticker),
        0,
    )


def apply_decision(decision: Decision, expected_number_of_stocks: int) -> int:
    """Validate and apply one decision, returning the resulting holding."""
    decision = Decision.model_validate(decision)
    with _lock:
        positions = {p["ticker"]: p["number_of_stocks"] for p in read_portfolio()}
        current = positions.get(decision.ticker, 0)
        if current != expected_number_of_stocks:
            raise ValueError("Holding changed during decision; run the analysis again")
        if decision.action == "hold":
            return current
        delta = decision.number_of_stocks
        if decision.action == "sell":
            delta = -delta
        updated = current + delta
        if updated < 0:
            raise ValueError("Cannot sell more stocks than the portfolio holds")
        if updated:
            positions[decision.ticker] = updated
        else:
            positions.pop(decision.ticker, None)

        _write_portfolio([
            {"ticker": ticker, "number_of_stocks": count}
            for ticker, count in positions.items()
        ])
        return updated


def _write_portfolio(positions: list[dict]) -> None:
    with _lock:
        # Replace atomically so a failed write cannot truncate the portfolio.
        PORTFOLIO_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=PORTFOLIO_PATH.parent,
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                json.dump(
                    positions,
                    temporary,
                    indent=2,
                    ensure_ascii=False,
                )
                temporary.write("\n")
            temporary_path.replace(PORTFOLIO_PATH)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


def sync_from_alpaca() -> None:
    """Replace the local record with one validated broker positions snapshot."""
    from .trading import get_client

    with _lock:
        positions = []
        for holding in get_client().get_all_positions():
            quantity = Decimal(str(holding.qty))
            if not quantity.is_finite() or quantity < 0 or quantity != quantity.to_integral_value():
                raise ValueError(f"Cannot store Alpaca holding {holding.symbol}: {quantity}; expected whole long shares")
            if quantity:
                positions.append(Position(ticker=holding.symbol, number_of_stocks=int(quantity)).model_dump())
        if len({p["ticker"] for p in positions}) != len(positions):
            raise ValueError("Alpaca positions contain duplicate tickers")
        _write_portfolio(sorted(positions, key=lambda p: p["ticker"]))
    print(f"[Portefølje] Synkronisert {len(positions)} beholdninger fra Alpaca til {PORTFOLIO_PATH}", flush=True)


def set_holding(ticker: str, quantity: int) -> None:
    """Persist an absolute broker-confirmed holding, making reconciliation repeatable."""
    current = get_number_of_stocks(ticker)
    delta = quantity - current
    if delta:
        apply_decision(
            Decision(
                ticker=ticker,
                action="buy" if delta > 0 else "sell",
                number_of_stocks=abs(delta),
            ),
            current,
        )
