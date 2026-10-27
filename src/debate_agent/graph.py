from langgraph.graph import StateGraph, START, END

from .state import DebateState

from .nodes import (
    validate_input,
    bull_opening,
    bear_opening,
    bull_rebuttal,
    bear_rebuttal,
    assemble_debate,
)

builder = StateGraph(DebateState)

builder.add_node("validate_input", validate_input)

builder.add_node("bull_opening", bull_opening)
builder.add_node("bear_opening", bear_opening)

builder.add_node("bull_rebuttal", bull_rebuttal)
builder.add_node("bear_rebuttal", bear_rebuttal)

builder.add_node("assemble_debate", assemble_debate)


builder.add_edge(START, "validate_input")

builder.add_edge("validate_input", "bull_opening")
builder.add_edge("validate_input", "bear_opening")

builder.add_edge(
    ["bull_opening", "bear_opening"],
    "bull_rebuttal"
)

builder.add_edge(
    ["bull_opening", "bear_opening"],
    "bear_rebuttal"
)

builder.add_edge(
    ["bull_rebuttal", "bear_rebuttal"],
    "assemble_debate"
)

builder.add_edge("assemble_debate", END)

graph = builder.compile()