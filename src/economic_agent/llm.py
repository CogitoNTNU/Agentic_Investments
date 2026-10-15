import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from src.economic_agent.tools import FINANCIAL_TOOLS
from src.economic_agent.schemas import EconomicAnalysis


load_dotenv()


MODEL = os.getenv("MODEL")
IDUN_API_KEY = os.getenv("IDUN_API_KEY")
IDUN_BASE_URL = os.getenv("IDUN_BASE_URL")


if not MODEL:
    raise ValueError("MODEL mangler i .env")

if not IDUN_API_KEY:
    raise ValueError("IDUN_API_KEY mangler i .env")

if not IDUN_BASE_URL:
    raise ValueError("IDUN_BASE_URL mangler i .env")


llm = ChatOpenAI(
    model=MODEL,
    api_key=IDUN_API_KEY,
    base_url=IDUN_BASE_URL,
    temperature=0
)


llm_with_tools = llm.bind_tools(
    FINANCIAL_TOOLS
)


structured_llm = llm.with_structured_output(
    EconomicAnalysis
)