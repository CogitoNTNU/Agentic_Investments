from langgraph.graph import END, START, StateGraph

from ..decision_agent.agent import load_portfolio, make_decision
from .nodes import (
    bear_opening,
    bear_rebuttal,
    bull_opening,
    bull_rebuttal,
    validate_input,
)
from .state import DebateState

builder = StateGraph(DebateState)

builder.add_node("validate_input", validate_input)
builder.add_node("load_portfolio", load_portfolio)
builder.add_node("make_decision", make_decision)

builder.add_node("bull_opening", bull_opening)
builder.add_node("bear_opening", bear_opening)

builder.add_node("bull_rebuttal", bull_rebuttal)
builder.add_node("bear_rebuttal", bear_rebuttal)

builder.add_edge(START, "validate_input")

builder.add_edge("validate_input", "load_portfolio")
builder.add_edge("load_portfolio", "bull_opening")
builder.add_edge("load_portfolio", "bear_opening")

builder.add_edge(["bull_opening", "bear_opening"], "bull_rebuttal")

builder.add_edge(["bull_opening", "bear_opening"], "bear_rebuttal")

builder.add_edge(["bull_rebuttal", "bear_rebuttal"], "make_decision")
builder.add_edge("make_decision", END)

graph = builder.compile()

# Reviews reuse the debate, then pass its result to the decision agent before execution.
review_debate = builder.compile(interrupt_before=["make_decision"])
