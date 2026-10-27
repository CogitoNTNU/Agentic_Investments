from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    ticker: str
    messages: Annotated[list[AnyMessage], add_messages]
    report_text: NotRequired[str]
    report_id: NotRequired[str]
    report_form: NotRequired[str]
    report_date: NotRequired[str]
    filing_date: NotRequired[str]
    report_url: NotRequired[str]
    company_name: NotRequired[str]
    summary: NotRequired[str]

    key_financial_points: NotRequired[list[str]]
    positive_factors: NotRequired[list[str]]
    risk_factors: NotRequired[list[str]]
    outlook_score: NotRequired[float]
    outlook_reasoning: NotRequired[str]
