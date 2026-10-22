from langchain.messages import SystemMessage
from langchain.messages import ToolMessage


from .tools import get_tools
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

tools, tools_by_name = get_tools()

BASE_URL = "https://llm.hpc.ntnu.no/v1"
MODEL_NAME = "deepseek-ai/DeepSeek-V4.1-Flash-1017"

def get_finance_agent():

    model_with_tools = ChatOpenAI(
        api_key = os.getenv("IDUN_API_KEY"),
        model=MODEL_NAME,
        base_url= BASE_URL
    ).bind_tools(tools)

    return model_with_tools


def llm_call(state: dict):
    """LLM decides whether to call a tool or not"""
    model_with_tools = get_finance_agent()

    return {
        "messages": [
            model_with_tools.invoke(
                [
                    SystemMessage(
                        content=f"""
                        You are a financial agent that can answer questions about companies and their financial data.
                        You have access to the following tools:
                        {tools}

                        Focus on objective facts about financial data and avoid speculation. 
                        If you don't know the answer, say "I don't know" instead of making up an answer.

                        If you know a company that is a direct competitor to the company in question, 
                        you can compare their financial data to provide context.
                        Use specifically the compare_key_metrics tool to compare key metrics of two companies.

                        Do not provide any personal opinions or speculations about the companies or their financial performance.
                        """
                    )
                ]
                + state["messages"]
            )
        ],
        "llm_calls": state.get('llm_calls', 0) + 1
    }


def tool_node(state: dict):
    """Performs the tool call"""

    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}