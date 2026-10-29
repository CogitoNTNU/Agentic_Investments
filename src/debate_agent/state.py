from typing import TypedDict


class DebateState(TypedDict, total=False):
    analysis_packet: dict
    bull_analysis: dict
    bear_analysis: dict
    bull_rebuttal: dict
    bear_rebuttal: dict
    debate_report: dict
    number_of_stocks: int
    decision: dict
