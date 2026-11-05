import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DecisionReasoning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rationale: str = Field(min_length=1)
    decisive_evidence: list[str] = Field(min_length=1)
    alternatives_rejected: str = Field(min_length=1)
    sizing_rationale: str = Field(min_length=1)
    risks_and_uncertainties: str = Field(min_length=1)
    change_conditions: str = Field(min_length=1)

    @field_validator("decisive_evidence", mode="before")
    @classmethod
    def decode_evidence_array(cls, value):
        # Some tool-call providers serialize nested arrays a second time.
        # Decode JSON only; ordinary prose still fails list validation.
        if isinstance(value, str):
            return json.loads(value)
        return value


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1)
    action: Literal["buy", "sell", "hold"]
    number_of_stocks: int = Field(strict=True, ge=0)
    # Keep execution journals and broker-order payloads backward compatible.
    reasoning: DecisionReasoning | None = Field(default=None, exclude=True)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("ticker must not be blank")
        return value

    @model_validator(mode="after")
    def validate_quantity(self):
        if self.action == "hold" and self.number_of_stocks != 0:
            raise ValueError("hold requires number_of_stocks = 0")
        if self.action != "hold" and self.number_of_stocks == 0:
            raise ValueError("buy/sell requires number_of_stocks > 0")
        return self


class ExplainedDecision(Decision):
    reasoning: DecisionReasoning = Field(exclude=True)

    @model_validator(mode="before")
    @classmethod
    def nest_flat_explanation(cls, value):
        # Run inside Pydantic so LangChain's tool parser also sees the repair.
        # Never overwrite a supplied nested explanation or alter trade fields.
        if isinstance(value, dict) and "reasoning" not in value:
            fields = DecisionReasoning.model_fields
            if any(key in value for key in fields):
                value = dict(value)
                value["reasoning"] = {key: value.pop(key) for key in fields if key in value}
        return value


class ReviewDecisionResponse(DecisionReasoning):
    """Flat model-facing schema; execution/report representations stay unchanged."""

    ticker: str = Field(min_length=1)
    action: Literal["buy", "sell", "hold"]
    number_of_stocks: int = Field(strict=True, ge=0)

    @model_validator(mode="before")
    @classmethod
    def accept_complete_nested_response(cls, value):
        # Accept the old valid representation, but never merge conflicting fields
        # or guess how to split free-form reasoning into required explanations.
        if isinstance(value, ExplainedDecision):
            return {**value.model_dump(), **value.reasoning.model_dump()}
        if (isinstance(value, dict) and isinstance(value.get("reasoning"), dict)
                and not (DecisionReasoning.model_fields.keys() & value.keys())):
            nested = value["reasoning"]
            if set(nested) <= DecisionReasoning.model_fields.keys():
                return {**{key: item for key, item in value.items() if key != "reasoning"}, **nested}
        return value

    def to_decision(self):
        return ExplainedDecision(
            ticker=self.ticker, action=self.action, number_of_stocks=self.number_of_stocks,
            reasoning={key: getattr(self, key) for key in DecisionReasoning.model_fields},
        )

    @model_validator(mode="after")
    def validate_trade_fields(self):
        decision = self.to_decision()
        self.ticker = decision.ticker
        return self
