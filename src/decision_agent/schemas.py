from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1)
    action: Literal["buy", "sell", "hold"]
    number_of_stocks: int = Field(strict=True, ge=0)

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
