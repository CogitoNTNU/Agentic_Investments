from langchain.messages import SystemMessage
from langchain.messages import ToolMessage
from langgraph_supervisor import create_supervisor


from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.news_agent.graph import graph as news_agent
from src.finance_agent.agent import agent as finance_agent
from src.economic_agent.graph import graph as economic_agent

load_dotenv()

BASE_URL = "https://llm.hpc.ntnu.no/v1"
MODEL_NAME = "Inferact/GLM-5.3-NVFP4"

model = ChatOpenAI(
    api_key = os.getenv("IDUN_API_KEY"),
    model=MODEL_NAME,
    base_url= BASE_URL
)

supervisor = create_supervisor(
    [news_agent, finance_agent, economic_agent],
    model=model,
    prompt="""

"""
).compile()

result = supervisor.invoke({"messages": [SystemMessage(content="Find recent news about Apple and analyze its financial data. Do not use news agent")]})
print(result)