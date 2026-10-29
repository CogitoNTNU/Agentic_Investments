<div align="center">

# Agentic Investments

<img src="docs/images/project-logo.png" width="40%" alt="Agentic Investments logo">

A multi-agent system for equity research and paper trading, built with LangGraph.

![Python](https://img.shields.io/badge/python-3.12-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-1.x-orange)
![License](https://img.shields.io/badge/license-MIT-green)
[![CI](https://github.com/CogitoNTNU/Agentic_Investments/actions/workflows/ci.yml/badge.svg)](https://github.com/CogitoNTNU/Agentic_Investments/actions/workflows/ci.yml)

</div>

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Agents](#agents)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Usage](#usage)
- [Testing](#testing)
- [Documentation](#documentation)
- [License](#license)

## Overview

Agentic Investments is a Cogito NTNU project that explores how a team of specialized LLM agents can research US equities and act on their findings. Each agent focuses on one source of information: market news, SEC filings, or fundamental financial data. A supervisor agent coordinates them and combines their output into a single view of a company. A set of Alpaca tools lets agents inspect a portfolio and place orders against a paper trading account.

The language models are served through the NTNU IDUN HPC inference endpoint, which exposes an OpenAI compatible API.

## Architecture

```
                      +------------------+
                      |    Supervisor    |
                      +--------+---------+
                               |
        +----------------------+----------------------+
        |                      |                      |
+-------v--------+    +--------v--------+    +--------v--------+
|   News agent   |    |  Finance agent  |    | Economic agent  |
| Yahoo Finance  |    |    yfinance     |    |    SEC EDGAR    |
+----------------+    +-----------------+    +-----------------+

+--------------------+          +---------------------------+
| Stockpicker agent  |          |       Alpaca tools        |
| Marketaux news     |          |  Paper trading execution  |
+--------------------+          +---------------------------+
```

## Agents

### Supervisor

`src/supervisor/agent.py` uses `langgraph-supervisor` to route a request between the news, finance, and economic agents and merge their results.

### Economic agent

`src/economic_agent/` analyzes the latest financial report for an S&P 500 company.

1. Resolves the ticker to a CIK and downloads the newest original 10-Q or 10-K from SEC EDGAR.
2. Extracts the report text and passes it to a tool-calling LLM.
3. The LLM computes metrics with deterministic tools such as growth rates, CAGR, profitability, liquidity and leverage ratios, free cash flow, return on equity, interest coverage, and simple projections.
4. A final step returns a structured `EconomicAnalysis` with a summary, key points, positive factors, risk factors, and an outlook score from 0 to 10.

The agent is also exposed as a LangChain tool (`economic_agent`) so it can be used by the supervisor.

### Finance agent

`src/finance/` analyzes a company's financial numbers and valuation from yfinance.

1. Fetches company info, key valuation metrics (market cap, P/E, forward P/E, PEG, dividend yield, beta) and annual and quarterly statements.
2. Computes ten financial features, such as growth, margins, return on equity, leverage, liquidity and free cash flow, with their annual and quarterly history.
3. An LLM selects the features that matter most for the company's sector, with sector defaults as a fallback.
4. Compares the company with up to three peers from the same S&P 500 sub-industry.
5. An analyst LLM interprets the data, and a final step returns a structured `FinanceAnalysis` with a financial score from 0 to 10.

The agent is exposed as a LangChain tool (`finance_agent`) for the supervisor. See [src/finance/README.md](src/finance/README.md) for details.

### Stockpicker agent

`src/stockpicker_agent/` is a news driven discovery pipeline that looks for S&P 500 companies worth investigating.

```
fetch_news -> filter_articles -> analyze_article -> select_candidates -> group_events
```

It fetches the last day of news from Marketaux, filters for S&P 500 tickers, classifies each article by event type, materiality, and confidence, and groups duplicate coverage of the same event.

### News agent

`src/news_agent/` provides a tool that fetches recent headlines for a single ticker from the Yahoo Finance RSS feed.

### Decision agent

`src/decision_agent/` receives the full state after the bull/bear debate.
The debate graph automatically loads the ticker's holding into
`state["number_of_stocks"]` before the debate, runs the decision agent after
`assemble_debate`, and returns `state["decision"]` in this fixed format:

```json
{"ticker": "AAPL", "action": "buy", "number_of_stocks": 3}
```

`action` is `buy`, `sell`, or `hold`. The quantity is the positive integer number
to buy or sell, not the target holding; `hold` requires 0. A decision to avoid
investing is `hold`; an existing position can also be reduced with `sell`.
After the decision, `state["number_of_stocks"]` contains the updated holding.

The agent can also receive arbitrary research directly, without a research schema.
Pass the ticker separately so its current holding can be read before the model runs:

```python
from src.decision_agent import run_decision

decision = run_decision("Any research text or debate output", ticker="AAPL")
```

Buy/sell decisions submit market DAY orders through the existing Alpaca paper
trading client. Set `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` in `.env`.
`hold` does not submit an order. The agent checks that the ticker's Alpaca holding
matches the local holding before submitting a trade; resolve any mismatch first.
Confirmed fills update `portfolio.json` in the project root, independent of
the working directory. The file contains only positions:

```json
[{"ticker": "AAPL", "number_of_stocks": 3}]
```

Executed buys add to the holding, executed sells subtract, and zero removes the
entry. Partial fills record only the executed quantity. Invalid model output,
overselling, changed holdings, or malformed JSON prevents order submission.
Rejected orders without fills leave the portfolio unchanged.

The agent polls order status for up to 30 seconds. If the order remains pending
(for example outside market hours), it raises `TimeoutError` and saves its client
order ID in `portfolio.pending.json`. This file also protects against repeat
submission following ambiguous network failures or a failed portfolio write.
Subsequent calls reconcile it before allowing another decision. To update an
existing order without requesting a new decision, call:

```python
from src.decision_agent import sync_pending_order

sync_pending_order()
```

This queries Alpaca and updates confirmed fills; it never submits another order.
While still pending it raises `RuntimeError`; call it again later. No background
worker is installed, so pending orders need a later call to synchronize. If a
submission failed before reaching Alpaca and lookup reports no matching order,
verify the client order ID in Alpaca before manually removing the pending file.
Keep the pending file if the submission outcome is uncertain.

Portfolio writes are atomic, and updates are serialized within one Python
process. Use one process and let this agent manage its tracked positions.
Each new `run_decision` invocation requests a new decision and can execute another
trade. The structured decision contains the requested trade size; JSON holdings
always reflect confirmed fills, including partial fills on canceled orders.

### Alpaca tools

`src/alpaca_tools/` wraps the Alpaca Trading API as LangChain tools. The client is always configured for paper trading. Tools are grouped by risk level:

| Group | Tools |
| --- | --- |
| `READ_ONLY_TOOLS` | Account info, portfolio history, market clock, asset info, positions, orders |
| `EXECUTION_TOOLS` | Market, limit, stop, stop limit, trailing stop, and bracket orders; replace or cancel an order; close a position |
| `ADMIN_TOOLS` | Cancel all orders, close all positions |

Give each agent only the groups it needs.

## Project Structure

```
Agentic_Investments/
├── docs/                    # MkDocs documentation
├── src/
│   ├── alpaca_tools/        # Alpaca paper trading tools
│   ├── economic_agent/      # SEC filing analysis agent
│   ├── finance/             # yfinance financial analysis agent
│   ├── news_agent/          # Yahoo Finance news tool
│   ├── stockpicker_agent/   # Marketaux news discovery pipeline
│   ├── supervisor/          # Multi-agent supervisor
│   └── model.py             # Shared LLM client
├── tests/                   # Pytest suite
├── mkdocs.yml
└── pyproject.toml
```

## Getting Started

### Prerequisites

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- Access to the NTNU IDUN LLM endpoint
- API keys for Alpaca (paper trading) and Marketaux, if you use those components

### Installation

```bash
git clone https://github.com/CogitoNTNU/Agentic_Investments.git
cd Agentic_Investments
uv sync
```

Install the development and documentation tools as well:

```bash
uv sync --group dev --group docs
uv run pre-commit install
```

Some components rely on packages that are not yet declared in `pyproject.toml`. Install them if you plan to use those agents:

```bash
uv add yfinance alpaca-py feedparser langgraph-supervisor
```

## Configuration

Create a `.env` file in the project root:

```env
# LLM endpoint
IDUN_API_KEY=your-idun-api-key
IDUN_BASE_URL=https://llm.hpc.ntnu.no/v1
MODEL=your-model-name

# SEC EDGAR (required by the economic agent)
SEC_USER_AGENT="Your App Name your.email@example.com"

# Marketaux (required by the stockpicker agent)
MARKETAUX_API_KEY=your-marketaux-key

# Alpaca paper trading
ALPACA_API_KEY=your-alpaca-key
ALPACA_SECRET_KEY=your-alpaca-secret
```

The `.env` file is ignored by git. Never commit API keys.

## Usage

Analyze the latest SEC filing for a company:

```bash
uv run python -m src.economic_agent.main AAPL
```

Run the stockpicker discovery pipeline:

```bash
uv run python -m src.stockpicker_agent.test
```

Run the supervisor:

```bash
uv run python src/supervisor/agent.py
```

Use the economic agent as a tool from Python:

```python
from src.economic_agent.main import economic_agent

result = economic_agent.invoke({"ticker": "MSFT"})
print(result["summary"], result["outlook_score"])
```

## Testing

```bash
uv run pytest
```

With coverage:

```bash
uv run pytest --cov=src --cov-report=html
```

Continuous integration runs the test suite on every push and pull request to `main`, then publishes the documentation to GitHub Pages.

## Documentation

Build and serve the documentation locally:

```bash
uv run mkdocs serve
```

## Disclaimer

This project is for research and educational purposes only. Nothing it produces is financial advice. Trading tools are configured for Alpaca paper trading and should not be pointed at a live account.

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
