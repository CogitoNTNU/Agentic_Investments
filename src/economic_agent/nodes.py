from langchain_core.messages import SystemMessage, HumanMessage

from src.economic_agent.state import AgentState
from src.economic_agent.llm import llm_with_tools, structured_llm
from src.economic_agent.prompts import ANALYST_PROMPT, FINAL_ANALYSIS_PROMPT
from src.economic_agent.report_fetcher import fetch_latest_quarterly_report


def fetch_report_node(state: AgentState):

    company_query = state["company_query"]

    report = fetch_latest_quarterly_report(company_query)

    print(f"Report found for: {report['company_name']}")
    print(f"Report URL: {report['report_url']}")

    return report


def prepare_analysis_node(state: AgentState):

    message = HumanMessage(
        content=f"""
Analyse the following quarterly report.

Company:
{state["company_name"]}

Report URL:
{state["report_url"]}

QUARTERLY REPORT:

{state["report_text"]}
"""
    )

    return {
        "messages": [message]
    }


def financial_agent_node(state: AgentState):

    messages = [
        SystemMessage(
            content=ANALYST_PROMPT
        )
    ] + state["messages"]

    response = llm_with_tools.invoke(
        messages
    )

    return {
        "messages": [response]
    }


def route_after_agent(state: AgentState):

    last_message = state["messages"][-1]

    if last_message.tool_calls:
        return "tools"

    return "final_analysis"


def final_analysis_node(state: AgentState):

    messages = [
        SystemMessage(
            content=FINAL_ANALYSIS_PROMPT
        )
    ] + state["messages"]

    analysis = structured_llm.invoke(
        messages
    )

    return {
        "company_name": analysis.company_name,
        "summary": analysis.summary,
        "key_financial_points": analysis.key_financial_points,
        "positive_factors": analysis.positive_factors,
        "risk_factors": analysis.risk_factors,
        "outlook_score": analysis.outlook_score,
        "outlook_reasoning": analysis.outlook_reasoning
    }