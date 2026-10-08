from pydantic import BaseModel, Field
from typing import Literal

class NewsEvent(BaseModel):
    ticker: str

    event_type: Literal[
        "earnings",
        "guidance",
        "major_contract",
        "merger_acquisition",
        "partnership",
        "product_launch",
        "regulatory",
        "lawsuit",
        "management_change",
        "financing",
        "insider_activity",
        "other",
    ]


    summary: str

    sentiment: float = Field(ge=-1, le=1)
    materiality: float = Field(ge=0, le=10)
    novelty: float = Field(ge=0, le=10)
    confidence: float = Field(ge=0, le=1)

    investigate: bool



class NewsAnalysis(BaseModel):
    events: list[NewsEvent]