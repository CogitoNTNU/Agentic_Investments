from langgraph.graph import StateGraph, START, END

from .state import NewsDiscoveryState
from .nodes import fetch_news, analyze_article

builder = StateGraph(NewsDiscoveryState)

builder.add_node("fetch_news", fetch_news)
builder.add_node("analyze_article", analyze_article)

builder.add_edge(START, "fetch_news")
builder.add_edge("fetch_news", "analyze_article")
builder.add_edge("analyze_article", END)

graph = builder.compile()