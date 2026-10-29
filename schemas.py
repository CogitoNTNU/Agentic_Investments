from pydantic import BaseModel, Field 

class stockRecommendation(BaseModel):
    forkortelse : str = Field(
        description="Forkortelse til selskapet, for eksempel NVDA, MSFT eller AAPL"
    )

    bedriftsnavn : str = Field(
        description="Navnet til bedriften"
    )

    score : float = Field(
        ge=1,
        le=10,
        description="Investeringsscoren fra 1 til 10"
    )

    reasoning : str = Field(
        description="Begrunnelse for investeringsscoren du har gitt"
    )


class portfolioRecommentation(BaseModel): 
    stocks: list[stockRecommendation] = Field(
        min_length = 10,
        max_length = 10,
        description = "Nøyaktig 10 aksje-anbefalinger"
    )
