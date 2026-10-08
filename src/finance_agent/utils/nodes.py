from langchain.messages import SystemMessage
from langchain.messages import ToolMessage


from .tools import get_tools
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

tools, tools_by_name = get_tools()

BASE_URL = "https://llm.hpc.ntnu.no/v1"
MODEL_NAME = "Inferact/GLM-5.3-NVFP4"

model_with_tools = ChatOpenAI(
    api_key = os.getenv("IDUN_API_KEY"),
    model=MODEL_NAME,
    base_url= BASE_URL
).bind_tools(tools)


def llm_call(state: dict):
    """LLM decides whether to call a tool or not"""

    return {
        "messages": [
            model_with_tools.invoke(
                [
                    SystemMessage(
                        content="You are a helpful assistant tasked with performing arithmetic on a set of inputs."
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