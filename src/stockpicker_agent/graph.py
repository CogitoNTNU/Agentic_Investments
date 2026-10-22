from langgraph.graph import StateGraph, START, END

from .state import NewsDiscoveryState
from .nodes import (
    fetch_news,
    filter_articles,
    analyze_article,
    select_candidates,
    group_events,
)

builder = StateGraph(NewsDiscoveryState)

builder.add_node("fetch_news", fetch_news)
builder.add_node("filter_articles", filter_articles)
builder.add_node("analyze_article", analyze_article)
builder.add_node("select_candidates", select_candidates)
builder.add_node("group_events", group_events)

builder.add_edge(START, "fetch_news")
builder.add_edge("fetch_news", "filter_articles")
builder.add_edge("filter_articles", "analyze_article")
builder.add_edge("analyze_article", "select_candidates")
builder.add_edge("select_candidates", "group_events")
builder.add_edge("group_events", END)

graph = builder.compile()