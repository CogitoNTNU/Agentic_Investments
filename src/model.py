# import os

# # from typing import Any
# from dotenv import load_dotenv
# from openai import OpenAI

# # from src.schemas import AgentDecision

# load_dotenv()

# client = OpenAI(
#     base_url="https://llm.hpc.ntnu.no/v1", api_key=os.getenv("IDUN_API_KEY")
# )


# class Model:
#     """Anything used as an agent model must implement this interface."""

#     # def decide(
#     #     self,
#     #     history: list[dict[str, str]],
#     #     tools: list[Any] | None = None,
#     # ) -> dict[str, Any]:
#     #     "Returnerer enten en tool eller svar"

#     def ask(self, prompt: str) -> str:
#         response = client.chat.completions.create(
#             model="Inferact/GLM-5.3-NVFP4",
#             messages=[{"role": "user", "content": prompt}],
#         )
#         return response.choices[0].message.content or ""

# model.py

import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel


load_dotenv()


BASE_URL = "https://llm.hpc.ntnu.no/v1"
MODEL_NAME = "Inferact/GLM-5.3-NVFP4"


def get_model():
    api_key = os.getenv("IDUN_API_KEY")

    if not api_key:
        raise ValueError("IDUN_API_KEY is not set")

    client = AsyncOpenAI(
        base_url=BASE_URL,
        api_key=api_key,
    )

    return OpenAIChatCompletionsModel(
        model=MODEL_NAME,
        openai_client=client,
    )
