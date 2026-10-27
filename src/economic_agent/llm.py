from src.model import get_model
from src.economic_agent.tools import FINANCIAL_TOOLS
from src.economic_agent.schemas import EconomicAnalysis


llm = get_model()
llm.temperature = 0


llm_with_tools = llm.bind_tools(
    FINANCIAL_TOOLS
)


structured_llm = llm.with_structured_output(
    EconomicAnalysis
)
