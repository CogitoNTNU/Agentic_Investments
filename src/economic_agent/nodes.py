from langchain_core.messages import HumanMessage, SystemMessage

from src.economic_agent.llm import llm_with_tools, structured_llm
from src.economic_agent.prompts import ANALYST_PROMPT, FINAL_ANALYSIS_PROMPT
from src.economic_agent.report_fetcher import (
    download_report,
    fetch_latest_quarterly_report,
)
from src.economic_agent.state import AgentState


def fetch_report_node(state: AgentState):
    if state.get("report_id"):
        report = {
            key: state[key]
            for key in (
                "ticker",
                "company_name",
                "report_id",
                "report_url",
                "report_form",
                "report_date",
                "filing_date",
            )
        }
        return download_report(report)
    return fetch_latest_quarterly_report(state["ticker"])


def prepare_analysis_node(state: AgentState):

    message = HumanMessage(
        content=f"""
Analyse the following SEC financial report.

Ticker: {state["ticker"]}
Form: {state["report_form"]}
Period ended: {state["report_date"]}
Filed: {state["filing_date"]}

Company:
{state["company_name"]}

Report URL:
{state["report_url"]}

QUARTERLY REPORT:

{state["report_text"]}
"""
    )

    return {"messages": [message]}


def financial_agent_node(state: AgentState):

    messages = [SystemMessage(content=ANALYST_PROMPT)] + state["messages"]

    response = llm_with_tools.invoke(messages)

    return {"messages": [response]}


def route_after_agent(state: AgentState):

    last_message = state["messages"][-1]

    if last_message.tool_calls:
        return "tools"

    return "final_analysis"


def final_analysis_node(state: AgentState):

    messages = [SystemMessage(content=FINAL_ANALYSIS_PROMPT)] + state["messages"]

    analysis = structured_llm.invoke(messages)

    return {
        "summary": analysis.summary,
        "key_financial_points": analysis.key_financial_points,
        "positive_factors": analysis.positive_factors,
        "risk_factors": analysis.risk_factors,
        "outlook_score": analysis.outlook_score,
        "outlook_reasoning": analysis.outlook_reasoning,
    }
