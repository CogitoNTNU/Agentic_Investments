import asyncio

from tools import *
from agents import Runner, set_tracing_disabled
from models import estimates_agent
set_tracing_disabled(disabled=True)

async def main():
    result = await Runner.run(
        estimates_agent,
        "Retrieve financial estimates for the stock ticker symbol 'AAPL'."
    )
    print("Agent Result:", result)

if __name__ == "__main__":
    asyncio.run(main())