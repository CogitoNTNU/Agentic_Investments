import json

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from openai import APIError
from pydantic import ValidationError

from src.finance.data_fetcher import fetch_financial_data, normalize_ticker
from src.finance.features import (
    FEATURE_UNITS,
    available_features,
    compute_features,
    default_features,
)
from src.finance.llm import feature_selector_llm, llm_with_tools, structured_llm
from src.finance.peers import compare_with_peers, fetch_peers, find_peers
from src.finance.prompts import (
    ANALYST_PROMPT,
    FEATURE_SELECTION_PROMPT,
    FINAL_ANALYSIS_PROMPT,
)
from src.finance.state import FinanceState


def fetch_data_node(state: FinanceState):

    return fetch_financial_data(state["ticker"])


def compute_features_node(state: FinanceState):

    return compute_features(state["statements"])


def select_features_node(state: FinanceState):

    info = state["company_info"]
    features = state["features"]
    available = available_features(features)

    if not available:
        return {
            "selected_features": [],
            "feature_reasoning": "No features could be computed from the statements.",
        }

    message = HumanMessage(
        content=f"""
Company: {info["company_name"]}
Sector: {info["sector"]}
Industry: {info["industry"]}
Fiscal year: {state["features_period"]}

AVAILABLE FEATURES (name: value, unit):

{json.dumps({f: [features[f], FEATURE_UNITS[f]] for f in available}, indent=2)}
"""
    )

    try:
        selection = feature_selector_llm.invoke(
            [SystemMessage(content=FEATURE_SELECTION_PROMPT), message]
        )
        # The schema allows every feature, so drop picks that have no value.
        selected = list(dict.fromkeys(f for f in selection.features if f in available))
        reasoning = selection.reasoning
    except (APIError, OutputParserException, ValidationError):
        selected = []

    if not selected:
        selected = default_features(info["sector"], available)
        reasoning = f"Default features for the {info['sector']} sector."

    return {"selected_features": selected, "feature_reasoning": reasoning}


def fetch_peers_node(state: FinanceState):

    ticker = state["ticker"]

    if state.get("peers"):
        peers = [normalize_ticker(peer) for peer in state["peers"]]
        peers = [peer for peer in dict.fromkeys(peers) if peer != ticker]
    else:
        peers = find_peers(ticker, state["key_metrics"]["market_cap"])

    peer_data = fetch_peers(peers)

    return {
        "peers": list(peer_data),
        "peer_data": peer_data,
        "peer_comparison_data": compare_with_peers(
            state["key_metrics"],
            state["features"],
            state["selected_features"],
            peer_data,
        ),
    }


def prepare_analysis_node(state: FinanceState):

    info = state["company_info"]

    selected = {
        feature: {
            "unit": FEATURE_UNITS[feature],
            "latest": state["features"][feature],
            "annual": state["feature_history"].get(feature, {}),
            "quarterly": state["quarterly_feature_history"].get(feature, {}),
        }
        for feature in state["selected_features"]
    }

    peers = {
        peer["ticker"]: peer["company_name"] for peer in state["peer_data"].values()
    }

    message = HumanMessage(
        content=f"""
Analyse the following financial data.

Ticker: {state["ticker"]}
Company: {info["company_name"]}
Sector: {info["sector"]}
Industry: {info["industry"]}
Currency: {info["currency"]}
Latest fiscal year: {state["features_period"]}

KEY METRICS:

{json.dumps(state["key_metrics"], indent=2)}

SELECTED FEATURES (history by period end):

{json.dumps(selected, indent=2)}

WHY THESE FEATURES:

{state["feature_reasoning"]}

PEERS:

{json.dumps(peers, indent=2) if peers else "No peers found."}

COMPARISON WITH PEER MEDIAN:

{json.dumps(state["peer_comparison_data"], indent=2) if peers else "Not available."}
"""
    )

    return {"messages": [message]}


def analyst_node(state: FinanceState):

    messages = [SystemMessage(content=ANALYST_PROMPT)] + state["messages"]

    response = llm_with_tools.invoke(messages)

    return {"messages": [response]}


def route_after_agent(state: FinanceState):

    last_message = state["messages"][-1]

    if last_message.tool_calls:
        return "tools"

    return "final_analysis"


def final_analysis_node(state: FinanceState):

    messages = [SystemMessage(content=FINAL_ANALYSIS_PROMPT)] + state["messages"]

    analysis = structured_llm.invoke(messages)

    return analysis.model_dump()
