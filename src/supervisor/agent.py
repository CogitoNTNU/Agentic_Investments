from langchain.messages import SystemMessage
from langchain.messages import ToolMessage
from langgraph_supervisor import create_supervisor


from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.news_agent.news_agent import news_graph as news_agent
from src.finance_agent.agent import agent as finance_agent
from src.economic_agent.graph import graph as economic_agent
from src.debate_agent.graph import graph as debate_agent
from src.supervisor.prompt import SUPERVISOR_PROMPT

load_dotenv()

BASE_URL = "https://llm.hpc.ntnu.no/v1"
MODEL_NAME = "Inferact/GLM-5.3-NVFP4"

model = ChatOpenAI(
    api_key = os.getenv("IDUN_API_KEY"),
    model=MODEL_NAME,
    base_url= BASE_URL
)

supervisor = create_supervisor(
    [news_agent, finance_agent, economic_agent, debate_agent],
    model=model,
    prompt=SUPERVISOR_PROMPT,
).compile()

if __name__ == "__main__":
    result = supervisor.invoke({"messages": [SystemMessage(content="Research APPLE")]})
    print(result)
