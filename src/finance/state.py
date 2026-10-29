from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class FinanceState(TypedDict):
    ticker: str
    messages: Annotated[list[AnyMessage], add_messages]
    # Optional input; found from the S&P 500 sub-industry when left out.
    peers: NotRequired[list[str]]

    company_info: NotRequired[dict]
    key_metrics: NotRequired[dict]
    statements: NotRequired[dict]

    features_period: NotRequired[str | None]
    features: NotRequired[dict[str, float | None]]
    feature_history: NotRequired[dict[str, dict[str, float]]]
    quarterly_feature_history: NotRequired[dict[str, dict[str, float]]]
    selected_features: NotRequired[list[str]]
    feature_reasoning: NotRequired[str]

    peer_data: NotRequired[dict[str, dict]]
    peer_comparison_data: NotRequired[dict]

    summary: NotRequired[str]
    valuation_assessment: NotRequired[str]
    peer_comparison: NotRequired[list[str]]
    key_trends: NotRequired[list[str]]
    positive_factors: NotRequired[list[str]]
    risk_factors: NotRequired[list[str]]
    financial_score: NotRequired[float]
    score_reasoning: NotRequired[str]
