from src.finance.schemas import FeatureSelection, FinanceAnalysis
from src.finance.tools import FINANCE_TOOLS
from src.model import get_model

MODEL_NAME = "deepseek-ai/DeepSeek-V4.1-Flash-1017"


llm = get_model(MODEL_NAME)


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
