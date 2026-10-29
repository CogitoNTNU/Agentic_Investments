from src.model import FLASH_MODEL_NAME, get_model
from src.economic_agent.tools import FINANCIAL_TOOLS
from src.economic_agent.schemas import EconomicAnalysis


llm = get_model(FLASH_MODEL_NAME)
llm.temperature = 0


llm_with_tools = llm.bind_tools(
    FINANCIAL_TOOLS
)


structured_llm = llm.with_structured_output(
    EconomicAnalysis,
    # Flash can spend its whole answer on reasoning and return empty json_schema
    # content; a forced tool call always produces the structured arguments.
    method="function_calling",
)
