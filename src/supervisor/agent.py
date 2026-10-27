from langchain.messages import HumanMessage
from langchain.messages import ToolMessage
from langgraph_supervisor import create_supervisor


from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langchain.agents import create_agent

from src.news_agent.news_agent import get_stock_news_report
from src.finance_agent.agent import agent as finance_agent
from src.economic_agent.main import economic_agent as economic_report_tool
from src.debate_agent.tool import run_debate
from src.supervisor.prompt import SUPERVISOR_PROMPT

load_dotenv()

BASE_URL = "https://llm.hpc.ntnu.no/v1"
MODEL_NAME = "Inferact/GLM-5.3-NVFP4"

model = ChatOpenAI(
    api_key = os.getenv("IDUN_API_KEY"),
    model=MODEL_NAME,
    base_url= BASE_URL
)

# The supervisor only passes messages, so agents with their own state
# are wrapped as named tool-calling agents.
news_agent = create_agent(
    model,
    tools=[get_stock_news_report],
    name="news_agent",
    system_prompt="Call get_stock_news_report for the requested ticker and return the full JSON report unchanged.",
)

economic_agent = create_agent(
    model,
    tools=[economic_report_tool],
    name="economic_agent",
    system_prompt="Call economic_agent for the requested ticker and return the full analysis unchanged.",
)

debate_agent = create_agent(
    model,
    tools=[run_debate],
    name="debate_agent",
    system_prompt="Call run_debate with the analysis packet you receive and return the full debate report unchanged.",
)

supervisor = create_supervisor(
    [news_agent, finance_agent, economic_agent, debate_agent],
    model=model,
    prompt=SUPERVISOR_PROMPT,
).compile()

if __name__ == "__main__":
    result = supervisor.invoke({"messages": [HumanMessage(content="Research APPLE")]})
    print(result)
