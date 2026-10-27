from typing import Literal
from langgraph.graph import StateGraph, START, END
from langchain.messages import HumanMessage

from pathlib import Path

from utils.state import MessagesState
from utils.nodes import llm_call, tool_node


def should_continue(state: MessagesState) -> Literal["tool_node", END]:
    """Decide if we should continue the loop or stop based upon whether the LLM made a tool call"""

    messages = state["messages"]
    last_message = messages[-1]

    # If the LLM makes a tool call, then perform an action
    if last_message.tool_calls:
        return "tool_node"

    # Otherwise, we stop (reply to the user)
    return END

# Build workflow
agent_builder = StateGraph(MessagesState)

# Add nodes
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)

# Add edges to connect nodes
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges(
    "llm_call",
    should_continue,
    ["tool_node", END]
)
agent_builder.add_edge("tool_node", "llm_call")

# Compile the agent
agent = agent_builder.compile(name="finance_agent")

if __name__ == "__main__":
    # Invoke
    messages = [HumanMessage(content="Give me an analysis of Apple Inc.'s financial data and compare it to Microsoft.")]
    messages = agent.invoke({"messages": messages})
    for m in messages["messages"]:
        m.pretty_print()