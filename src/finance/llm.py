from src.finance.schemas import FeatureSelection, FinanceAnalysis
from src.finance.tools import FINANCE_TOOLS
from src.model import FLASH_MODEL_NAME, get_model


llm = get_model(FLASH_MODEL_NAME)
llm.temperature = 0


llm_with_tools = llm.bind_tools(
    FINANCE_TOOLS
)


feature_selector_llm = llm.with_structured_output(
    FeatureSelection,
    method="function_calling",
)


structured_llm = llm.with_structured_output(
    FinanceAnalysis,
    method="function_calling",
)
