"""Model abstractions.

For the first exercise we use a deterministic ScriptedModel instead of
calling a real LLM. This lets us learn and test the agent loop without
mixing in prompt/API/JSON-parsing problems yet.
"""

from typing import Protocol

from src.schemas import AgentDecision


class Model(Protocol):
    """Anything used as an agent model must implement this interface."""

    