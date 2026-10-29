from typing import Literal
from pydantic import BaseModel, Field

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


class FinanceAnalysis(BaseModel):
    summary: str = Field(
        description="Short summary of the company's financial position and valuation."
    )
    valuation_assessment: str = Field(
        description="Assessment of the valuation metrics (P/E, forward P/E, PEG, dividend yield), also relative to peers."
    )
    peer_comparison: list[str] = Field(
        description="Observations from comparing the company with its peers."
    )
    key_trends: list[str] = Field(
        description="Important annual and quarterly trends in the selected features."
    )
    positive_factors: list[str] = Field(
        description="Financial strengths of the company."
    )
    risk_factors: list[str] = Field(
        description="Financial weaknesses or risks of the company."
    )
    financial_score: float = Field(
        ge=0,
        le=10,
        description="Score from 0 to 10 describing how strong the company's financial position and valuation are.",
    )
    score_reasoning: str = Field(
        description="Short explanation and justification of the financial score."
    )
