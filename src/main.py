# main.py

import asyncio

from agents import Runner, set_tracing_disabled

from agent import stock_agent

set_tracing_disabled(True)


async def analyze_stock(ticker: str):

    ticker = ticker.strip().upper()

    prompt = f"""
    Analyze {ticker}.

    Use the available tools before producing
    your recommendation.
    """
    print("Starting agent")
    result = await Runner.run(
        stock_agent,
        prompt,
    )
    print("Agent finished")
    return result.final_output


async def main():

    ticker = input("Enter ticker: ")

    result = await analyze_stock(ticker)

    print(result)


if __name__ == "__main__":
    asyncio.run(main())
