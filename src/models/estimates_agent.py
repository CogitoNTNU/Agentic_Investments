import os
from agents import Agent, ModelSettings, OpenAIChatCompletionsModel, AsyncOpenAI

from tools import retrieve_estimates
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

def get_model():
    IDUN_API_KEY = os.getenv("IDUN_API_KEY")

    return OpenAIChatCompletionsModel(
        model="Inferact/GLM-5.3-NVFP4",
        openai_client= AsyncOpenAI(
            base_url="https://llm.hpc.ntnu.no/v1",
            api_key=IDUN_API_KEY,
        )
    )

estimates_agent = Agent(
    name="Financial Estimates Agent",
    model=get_model(),
    model_settings=ModelSettings(extra_body={"reasoning_effort": "medium"}),
    instructions=f"""
        You are a financial estimates agent. Your task is to retrieve financial estimates for a given stock ticker symbol. Use the provided tools to fetch the necessary data.
    """,
    tools=[
        retrieve_estimates
    ],
)