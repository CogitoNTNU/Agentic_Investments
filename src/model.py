"""Model abstractions.

For the first exercise we use a deterministic ScriptedModel instead of
calling a real LLM. This lets us learn and test the agent loop without
mixing in prompt/API/JSON-parsing problems yet.
"""

from typing import Protocol

# from src.schemas import AgentDecision

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url="https://llm.hpc.ntnu.no/v1",
    api_key=os.getenv("IDUN_API_KEY")
)

class Model(Protocol):
    """Anything used as an agent model must implement this interface."""

    