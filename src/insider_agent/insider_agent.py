"""
US Insider Sub-Agent.
Pipeline: main agent -> insider agent (this file) -> main agent -> decision agent
"""
from pathlib import Path
import sys
from typing import List, Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.insider_agent.insider_tools import fetch_us_insider_transactions


# ---------- Output Schema ----------
class InsiderTrade(BaseModel):
    filing_date: str
    insider_name: str
    role_or_relation: str
    transaction_type: Literal["buy", "sell", "grant", "exercise", "other"]
    shares: float
    price_per_share: Optional[float] = None
    value: Optional[float] = None
    source_url: Optional[str] = None


class StockInsiderAnalysis(BaseModel):
    ticker: str
    market: Literal["US"] = "US"
    status: Literal["ok", "no_trades", "error"]
    period_days: int
    net_insider_volume: float = 0.0
    net_insider_value: float = 0.0
    sentiment: Literal["strongly_bullish", "bullish", "neutral", "bearish", "strongly_bearish", "unknown"] = "unknown"
    trades: List[InsiderTrade] = Field(default_factory=list, max_length=10)
    note: Optional[str] = None


class SingleInsiderReport(BaseModel):
    stock: StockInsiderAnalysis


def _derive_insider_sentiment(net_val: float, buy_count: int, sell_count: int) -> str:
    if buy_count == 0 and sell_count == 0:
        return "neutral"
    if buy_count > 0 and sell_count == 0:
        return "strongly_bullish" if net_val > 2_000_000 else "bullish"
    if sell_count > 0 and buy_count == 0:
        return "strongly_bearish" if net_val < -5_000_000 else "bearish"
    if net_val > 500_000:
        return "bullish"
    if net_val < -500_000:
        return "bearish"
    return "neutral"


def _error_report(ticker: str, days: int, reason: str) -> SingleInsiderReport:
    return SingleInsiderReport(
        stock=StockInsiderAnalysis(
            ticker=ticker,
            status="error",
            period_days=days,
            note=reason,
        )
    )


def run_insider_agent(ticker: str, days: int = 90) -> SingleInsiderReport:
    ticker = (ticker or "").strip().upper()
    days = max(1, min(days, 365))
    if not ticker:
        return _error_report(ticker, days, "No ticker provided")

    try:
        raw_trades = fetch_us_insider_transactions(ticker, days=days)
    except Exception as e:
        return _error_report(ticker, days, f"SEC data fetch failed: {str(e)}")

    if not raw_trades:
        return SingleInsiderReport(
            stock=StockInsiderAnalysis(
                ticker=ticker,
                status="no_trades",
                period_days=days,
                sentiment="neutral",
                note="No SEC Form 4 filings found for the selected period.",
            )
        )

    parsed_trades: List[InsiderTrade] = []
    net_shares = 0.0
    net_val = 0.0
    buys = 0
    sells = 0

    for trade in raw_trades[:10]:
        t_type = trade.get("transaction_type", "other")
        shares = float(trade.get("shares", 0.0))
        val = trade.get("value") or 0.0

        if t_type == "buy":
            net_shares += shares
            net_val += val
            buys += 1
        elif t_type == "sell":
            net_shares -= shares
            net_val -= val
            sells += 1

        parsed_trades.append(
            InsiderTrade(
                filing_date=trade.get("filing_date", ""),
                insider_name=trade.get("insider_name", "Unknown"),
                role_or_relation=trade.get("role", "Insider"),
                transaction_type=t_type if t_type in ["buy", "sell", "grant", "exercise"] else "other",
                shares=shares,
                price_per_share=trade.get("price_per_share"),
                value=trade.get("value"),
                source_url=trade.get("link"),
            )
        )

    sentiment = _derive_insider_sentiment(net_val, buys, sells)

    return SingleInsiderReport(
        stock=StockInsiderAnalysis(
            ticker=ticker,
            status="ok",
            period_days=days,
            net_insider_volume=round(net_shares, 2),
            net_insider_value=round(net_val, 2),
            sentiment=sentiment,
            trades=parsed_trades,
        )
    )


def report_to_llm_payload(report: SingleInsiderReport) -> str:
    return report.model_dump_json(exclude_none=True)


@tool
def get_stock_insider_report(ticker: str, days: int = 90) -> str:
    """Fetch recent US SEC Form 4 insider transactions for a given stock ticker.
    Returns transaction history, net volume, and directional sentiment.
    """
    return report_to_llm_payload(run_insider_agent(ticker, days))


# ---------- LangGraph Node ----------
class InsiderState(TypedDict, total=False):
    ticker: str
    days: int
    report: SingleInsiderReport
    payload: str


def insider_node(state: InsiderState) -> dict:
    return {"report": run_insider_agent(state["ticker"], state.get("days", 90))}


def insider_payload_node(state: InsiderState) -> dict:
    return {"payload": report_to_llm_payload(state["report"])}