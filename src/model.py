import os

from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()


BASE_URL = "https://llm.hpc.ntnu.no/v1"
GLM_MODEL_NAME = "Inferact/GLM-5.3-NVFP4"
# Default for all agents. GLM is ~9x slower: it reasons for thousands of tokens
# per call, which made a full supervisor run take ~19 minutes.
FLASH_MODEL_NAME = "deepseek-ai/DeepSeek-V4.1-Flash-1017"
MODEL_NAME = FLASH_MODEL_NAME


def get_model(model_name: str = MODEL_NAME):
    api_key = os.getenv("IDUN_API_KEY")

    if not api_key:
        raise ValueError("IDUN_API_KEY is not set")


    return ChatOpenAI(
        model=model_name,
        api_key= api_key,
        base_url= BASE_URL
    )
