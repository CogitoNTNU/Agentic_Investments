# main.py

import asyncio

from agents import Runner

from agent import stock_agent


async def analyze_stock(ticker: str):

    ticker = ticker.strip().upper()

    prompt = f"""
    Analyze {ticker}.

    Use the available tools before producing
    your recommendation.
    """

    result = await Runner.run(
        stock_agent,
        prompt,
    )

    return result.final_output


async def main():

    ticker = input("Enter ticker: ")

    result = await analyze_stock(ticker)

    print(
        result.model_dump_json(
            indent=2
        )
    )


if __name__ == "__main__":
    asyncio.run(main())