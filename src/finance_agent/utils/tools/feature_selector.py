from typing import Literal 
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

FinancialFeature = Literal[
    "revenue_growth",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "return_on_equity",
    "debt_to_equity",
    "current_ratio",
    "free_cash_flow",
    "free_cash_flow_margin",
    "earnings_growth",
]

class FeatureSelection(BaseModel):
    features: list[FinancialFeature] = Field(
        description="Selected available financial features",
        min_length = 1,
        max_length=6,
    )
    reasoning: str = Field(
        description="Brief explaination of the selection"
    )


llm = 