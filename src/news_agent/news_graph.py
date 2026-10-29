from langgraph.graph import END, START, StateGraph


from src.news_agent.news_agent import (
    news_node,
    payload_node,
)

from src.news_agent.news_agent import NewsState

builder = StateGraph(NewsState)
builder.add_node("run_news_agent", news_node)
builder.add_node("make_payload", payload_node)
builder.add_edge(START, "run_news_agent")
builder.add_edge("run_news_agent", "make_payload")
builder.add_edge("make_payload", END)
news_graph = builder.compile(name="news_graph")


# ---------- Manual test ----------
if __name__ == "__main__":
    out = news_graph.invoke({"ticker": "NVDA", "days": 7})
    print("\nPayload for the next agent:")
    print(out["payload"])
