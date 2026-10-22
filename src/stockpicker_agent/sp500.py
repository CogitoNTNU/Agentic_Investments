import csv
from pathlib import Path


def normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper().replace("-", ".")


def load_sp500() -> set[str]:

    path = Path(__file__).parent / "sp500.csv"

    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        tickers = {
            normalize_ticker(row["Symbol"])
            for row in reader
            if row.get("Symbol")
        }

    if len(tickers) < 450:
        raise ValueError(
            "S&P 500-listen ser ufullstendig ut. "
            f"Fant bare {len(tickers)} tickere."
        )

    return tickers