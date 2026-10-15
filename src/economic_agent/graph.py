from langgraph.graph import StateGraph, START, END 
from src.economic_agent.state import AgentState
from src.economic_agent.nodes import fetch_report_node, prepare_analysis_node, financial_agent_node, route_after_agent, final_analysis_node
from langgraph.prebuilt import ToolNode
from src.economic_agent.tools import FINANCIAL_TOOLS 

builder = StateGraph(AgentState)

builder.add_node("fetch_report", fetch_report_node)

builder.add_node("prepare_analysis", prepare_analysis_node)

builder.add_node("tools", ToolNode(FINANCIAL_TOOLS))

builder.add_node("financial_agent", financial_agent_node)

builder.add_node("final_analysis", final_analysis_node)

builder.add_edge(START, "fetch_report")

builder.add_edge("fetch_report", "prepare_analysis")

builder.add_edge("prepare_analysis", "financial_agent")

builder.add_conditional_edges("financial_agent", route_after_agent, {"tools": "tools", "final_analysis": "final_analysis"})

builder.add_edge("tools", "final_analysis")

builder.add_edge("final_analysis", END)

graph = builder.compile()