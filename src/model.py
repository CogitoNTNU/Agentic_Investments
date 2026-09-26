import os

# from typing import Any
from dotenv import load_dotenv
from openai import OpenAI

# from src.schemas import AgentDecision

load_dotenv()

client = OpenAI(
    base_url="https://llm.hpc.ntnu.no/v1", api_key=os.getenv("IDUN_API_KEY")
)


class Model:
    """Anything used as an agent model must implement this interface."""

    # def decide(
    #     self,
    #     history: list[dict[str, str]],
    #     tools: list[Any] | None = None,
    # ) -> dict[str, Any]:
    #     "Returnerer enten en tool eller svar"

    def ask(self, prompt: str) -> str:
        response = client.chat.completions.create(
            model="Inferact/GLM-5.3-NVFP4",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""
