from pydantic import BaseModel, Field

class EvidenceItem(BaseModel):
    id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    source: str = Field(min_length=1)
    as_of: str = Field(min_length=1)

class AnalysisPacket(BaseModel):
    ticker: str = Field(min_length=1)
    company_name: str = Field(min_length=1)
    as_of: str = Field(min_length=1)
    time_horizon: str = Field(min_length=1)
    evidence: list[EvidenceItem] = Field(min_length=1)

class Argument(BaseModel):
    claim: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)

class Thesis(BaseModel):
    summary: str = Field(min_length=1)
    arguments: list[Argument] = Field(min_length=1, max_length=4)
    acknowledged_weaknesses: list[str]
    missing_information: list[str]

class RebuttalPoint(BaseModel):
    opposing_argument_id: str = Field(min_length=1)
    response: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    concession: bool = False


class Rebuttal(BaseModel):
    responses: list[RebuttalPoint] = Field(min_length=1, max_length=4)
    revised_position: str = Field(min_length=1)
    conceded_points: list[str]
    unresolved_questions: list[str]