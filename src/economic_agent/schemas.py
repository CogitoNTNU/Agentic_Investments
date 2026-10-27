from pydantic import BaseModel, Field


class EconomicAnalysis(BaseModel):
    company_name: str = Field(description="Name of the company being analyzed.")
    summary: str = Field(
        description="Short summary of the company's financial situation and performance."
    )
    key_financial_points: list[str] = Field(
        description="Important financial observations from the company's report."
    )
    positive_factors: list[str] = Field(
        description="Factors that indicate positive future prospects."
    )
    risk_factors: list[str] = Field(
        description="Risk or weaknesses that may negatively affect the company."
    )
    outlook_score: float = Field(
        ge=0,
        le=10,
        description="Score from 0 to 10 describing how positive the company's future outlook is.",
    )
    outlook_reasoning: str = Field(
        description="Short explanation and justification of why the company received the outlook score."
    )
