from typing import TypedDict


class DebateState(TypedDict, total=False):
    account_snapshot: dict
    queue_source: str
    portfolio_source: str
    ticker: str
    in_portfolio: bool
    analysis_packet: dict
    bull_analysis: dict
    bear_analysis: dict
    bull_rebuttal: dict
    bear_rebuttal: dict
    number_of_stocks: int
    decision: dict
