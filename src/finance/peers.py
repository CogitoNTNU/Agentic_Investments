"""Find peer companies, fetch their data and compare them with the company."""

import csv
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median

import yfinance as yf

from src.finance.data_fetcher import KEY_METRICS, fetch_financial_data, normalize_ticker
from src.finance.features import compute_features

SP500_PATH = Path(__file__).resolve().parents[1] / "stockpicker_agent" / "sp500.csv"
MAX_PEERS = 3


def load_sub_industries() -> dict[str, str]:
    """Return {ticker: GICS sub-industry} for the S&P 500."""
    with SP500_PATH.open("r", encoding="utf-8", newline="") as file:
        return {
            normalize_ticker(row["Symbol"]): row["GICS Sub-Industry"]
            for row in csv.DictReader(file)
            if row.get("Symbol")
        }


def market_cap(ticker: str) -> float | None:
    try:
        return yf.Ticker(ticker).fast_info["marketCap"]
    except Exception:
        # yfinance raises many different errors for unknown or delisted tickers.
        return None


def find_peers(ticker: str, company_market_cap: float | None) -> list[str]:
    """Pick the S&P 500 companies in the same sub-industry that are closest in size."""
    sub_industries = load_sub_industries()
    sub_industry = sub_industries.get(ticker)
    if sub_industry is None:
        return []
    candidates = [
        other for other, industry in sub_industries.items()
        if industry == sub_industry and other != ticker
    ]
    if not company_market_cap or len(candidates) <= MAX_PEERS:
        return candidates[:MAX_PEERS]

    with ThreadPoolExecutor(max_workers=8) as pool:
        caps = dict(zip(candidates, pool.map(market_cap, candidates)))
    sized = [peer for peer in candidates if caps[peer]]
    sized.sort(key=lambda peer: abs(math.log(caps[peer] / company_market_cap)))
    return sized[:MAX_PEERS]


def fetch_peer(ticker: str) -> dict | None:
    try:
        data = fetch_financial_data(ticker)
    except Exception:
        # A peer that cannot be fetched is skipped rather than failing the analysis.
        return None
    return {
        "ticker": data["ticker"],
        "company_name": data["company_info"]["company_name"],
        "key_metrics": data["key_metrics"],
        "features": compute_features(data["statements"])["features"],
    }


def fetch_peers(peers: list[str]) -> dict[str, dict]:
    with ThreadPoolExecutor(max_workers=MAX_PEERS) as pool:
        results = pool.map(fetch_peer, peers)
    return {result["ticker"]: result for result in results if result}


def compare(value: float | None, peer_values: list[float | None], relative: bool) -> dict:
    values = [v for v in peer_values if v is not None]
    peer_median = median(values) if values else None
    difference = None
    if value is not None and peer_median:
        difference = (
            round((value - peer_median) / abs(peer_median) * 100, 2)
            if relative
            else round(value - peer_median, 2)
        )
    return {"company": value, "peer_median": peer_median, "difference": difference}


def compare_with_peers(
    key_metrics: dict, features: dict, selected: list[str], peer_data: dict
) -> dict:
    """Compare key metrics (% difference) and selected features (difference in the feature's unit)."""
    peers = list(peer_data.values())
    return {
        "key_metrics": {
            name: compare(
                key_metrics.get(name),
                [peer["key_metrics"].get(name) for peer in peers],
                relative=True,
            )
            for name in KEY_METRICS
        },
        "features": {
            name: compare(
                features.get(name),
                [peer["features"].get(name) for peer in peers],
                relative=False,
            )
            for name in selected
        },
    }
