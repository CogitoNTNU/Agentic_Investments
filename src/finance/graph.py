from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from src.finance.nodes import (
    analyst_node,
    compute_features_node,
    fetch_data_node,
    fetch_peers_node,
    final_analysis_node,
    prepare_analysis_node,
    route_after_agent,
    select_features_node,
)
from src.finance.state import FinanceState
from src.finance.tools import FINANCE_TOOLS

builder = StateGraph(FinanceState)

builder.add_node("fetch_data", fetch_data_node)

builder.add_node("compute_features", compute_features_node)

builder.add_node("select_features", select_features_node)

builder.add_node("fetch_peers", fetch_peers_node)

builder.add_node("prepare_analysis", prepare_analysis_node)

builder.add_node("analyst", analyst_node)

builder.add_node("tools", ToolNode(FINANCE_TOOLS))

builder.add_node("final_analysis", final_analysis_node)

builder.add_edge(START, "fetch_data")

builder.add_edge("fetch_data", "compute_features")

builder.add_edge("compute_features", "select_features")

builder.add_edge("select_features", "fetch_peers")

builder.add_edge("fetch_peers", "prepare_analysis")

builder.add_edge("prepare_analysis", "analyst")

builder.add_conditional_edges(
    "analyst",
    route_after_agent,
    {"tools": "tools", "final_analysis": "final_analysis"},
)

builder.add_edge("tools", "analyst")

builder.add_edge("final_analysis", END)

graph = builder.compile(name="finance_agent")
