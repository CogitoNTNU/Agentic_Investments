from langchain.messages import HumanMessage
from langchain.messages import ToolMessage
from langgraph_supervisor import create_supervisor


import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langchain.agents import create_agent

from src.debate_agent.tool import run_debate
from src.supervisor.research import gather_research_data
from src.supervisor.prompt import SUPERVISOR_PROMPT
from src.model import get_model

model = get_model()

# The supervisor only passes messages, so the debate agent with its own state
# is wrapped as a named tool-calling agent.
debate_agent = create_agent(
    model,
    tools=[run_debate],
    name="debate_agent",
    system_prompt="Call run_debate with the analysis packet you receive and return the full debate report unchanged.",
)

supervisor = create_supervisor(
    [debate_agent],
    model=model,
    # The data agents are independent, so one tool runs them in parallel.
    tools=[gather_research_data],
    prompt=SUPERVISOR_PROMPT,
).compile()

if __name__ == "__main__":
    result = supervisor.invoke({"messages": [HumanMessage(content="Research APPLE")]})
    print(result)
