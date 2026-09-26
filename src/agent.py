"""The core agent execution loop.

This is the most important file in the first exercise.

The agent should repeatedly:
    model decision
        -> tool call OR final answer

If the model requests a tool:
    execute tool
        -> save observation in history
        -> ask model again
"""

from src.schemas import FinalAnswer, ToolCall


class Agent:
    """Coordinates a model and a set of executable tools."""

    