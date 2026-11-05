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

`src/finance_agent/` is a ReAct style agent that pulls income statements, balance sheets, cash flow statements, and key valuation metrics (market cap, P/E, forward P/E, PEG, dividend yield, beta) from yfinance, and can compare two tickers.

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

Buy decisions submit DAY limit orders and sells submit DAY market orders through the existing Alpaca paper
trading client. Set `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` in `.env`.
`hold` does not submit an order. The agent checks that the ticker's Alpaca holding
matches the local holding before submitting a trade; resolve any mismatch first.
Buys use cash from the paper account, including proceeds from completed sales.
The pipeline sets the buy limit up to 2% above the latest trade and checks that
cash covers the entire order at that price. It first reserves cash for open buys.
An outstanding share-based market buy blocks further buys until its cost is known.
The initial $100,000 can grow through realized profits. Margin buying power adds
nothing to the cash budget. Run one trading pipeline per paper account so that
two writers cannot commit the same cash concurrently.
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
│   ├── finance_agent/       # yfinance fundamentals agent
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

Start the candidate queue (or choose **Start paper trading queue** in VS Code):

```bash
uv sync --group dev
uv run python -m src.main
```

For the four separate queues, select `data/simen.json` (10 candidates),
`data/nathania.json`, `data/sigurd.json`, or `data/brage.json` (9 each):

```bash
uv run python -m src.main --candidates data/simen.json
```

For a proposal-only holdings review, run
`python -m src.main --candidates data/sigurd.json --review-portfolio`.
The review researches Alpaca holdings first, saves their dated assessments to
`holdings_review.json` beside the queue, then researches the remaining candidates.
Each candidate runs through the original bull and bear openings and both rebuttals
before the decision agent evaluates the research and live account. HOLD passes
and SELL uses uncommitted shares. Only BUY proceeds to the portfolio comparison,
which can veto the buy, reduce its size, or propose a replacement. The report
records the debate and decision. Cash buys are capped at affordable whole shares
using the buffered limit price. If funds become insufficient before submission,
the buy is skipped and processing continues. Each
comparison uses a fresh account snapshot. Quantities are illustrative. The review leaves the queue intact
and submits no orders. Each run replaces the report for that directory.

To review and paper-trade the entire queue with one command, run
`python -m src.main --candidates data/sigurd.json --execute-review-all`.
Each candidate is compared against current Alpaca holdings before its action is
executed. A pass advances the queue. A pending replacement sale defers only its linked buy. Other candidates continue
using current cash and holdings. Leave the command running. After processing the other candidates, it checks pending
orders every 30 seconds and resumes eligible purchases automatically. After an
interruption, restart the same command to recover from the saved report.

To execute one saved recommendation on Alpaca paper, use the same queue and name
the candidate explicitly, for example
`python -m src.main --candidates data/sigurd.json --execute-review NVDA`.
Generate a review with this version first. A cash buy uses the checked DAY limit.
A replacement sells first. Rerun the same command after a pending or partial sale
to resume by broker order ID. The buy requires a full sale and a fresh cash check.
A pass or fully filled trade removes the candidate from the queue.
Before a replacement sale, the pipeline checks buffered buy cost against free cash
plus sale proceeds estimated with a 2% haircut. It reserves the planned buy budget
in the report and uses a fixed limit for that buy. Other candidates receive the
cash remaining after those reservations. The buy still requires actual cash after
the sale. Open broker buys are counted once when reserving funds.

If that pre-sale funding check fails, the portfolio comparison can reassess up to
twice using the saved bull/bear debate, original decision size, current cash,
and conservative sale proceeds. It may propose a smaller buy, a different
justified trim, a cash buy, or pass. Every revised order is checked again before
submission; no reassessment can rewrite an existing order intent or completed sale.
Old funding failures with no recorded orders are reopened for a full review on
the next batch run. Partially completed replacements are not automatically retried.

Review-mode decisions require a rationale, decisive evidence, rejected alternatives,
quantity justification, uncertainties and conditions that would change the decision.
These are saved as `decision_reasoning` in each candidate's review entry; the main
rationale is also logged. Existing order journals retain their original format.
Review prompts explicitly evaluate adding, keeping, trimming and exiting, including
evidence-backed profit-taking, thesis deterioration and excessive concentration.
A gain alone never requires selling, and missing research is not business deterioration.

Review sizing receives Alpaca latest-trade prices, cost basis when supplied by the
broker, and position weights against estimated equity (cash plus marked long holdings).
Buying power is never the portfolio-size denominator. Missing/invalid prices stop
the review before a new decision. Latest trades are not executable quotes; spread,
depth, fees, sector weights and correlations remain unknown unless separately supplied.
The prompts consider those uncertainties, switching costs and unnecessary turnover.
These are decision guidelines, not new mechanical stop-losses, profit targets,
exposure caps or liquidity checks. Existing cash guards and order recovery still apply.

Holdings assessment, final review decisions and replacement comparisons share an
evidence policy: a trim may be supported by concentration, valuation or credible
forward risk without waiting for business failure. Holding the full position must
be justified against trimming, using the same evidence standard as new purchases.
Unknown costs are not a demonstrated reason to reject a trade, and historical
cost basis is not a reason to avoid realizing a loss. Data gaps, sector-specific
valuation metrics and provisional monitoring thresholds must be identified.

The review provides code-calculated `portfolio_facts` (including the actual holding
count and available cash already net of reservations) and `sizing_examples`.
Reports save `risk_decision_math` and `planned_trade_math`, distinguishing the
requested size from the final capped size. Exposure scenarios show before/after
weights and portfolio loss for illustrative 20%, 40% and 60% single-stock declines.
They are not forecasts, loss limits, or automatic triggers. Proposed shares are
conditional on fills; fees/slippage and changes in other prices are not modeled.
The calculations do not guarantee that model prose will interpret them correctly.

Submitted and partially filled orders remain active until Alpaca reports a final
status. Rejected or expired orders become failed or incomplete outcomes, and
a sale followed by a failed buy is marked incomplete_replacement. These candidates
stay in the queue for a fresh review, while the batch proceeds with unrelated
candidates. Reruns reconcile saved order IDs and skip previously failed attempts
until a new review is generated. Older reports that marked submitted buys complete
are reconciled on restart. Reports with unresolved failures show needs_attention. See the report's
`execution.orders` for the last observed order statuses. Run one pipeline at a time.

These queues contain different tickers with the full discovery data preserved.
Process queues that share an Alpaca paper account sequentially.

The queue reads `data/news_discovery/grouped_candidates.json`, falling back to
`latest_candidates.json` when the grouped file is absent. It preserves file order
and processes each ticker once per run: research, debate, decision, then an Alpaca
paper order for `buy`/`sell`, or no order for `hold`. Discovery data is included in
the evidence. State contains `ticker`, `in_portfolio`, and `number_of_stocks`,
loaded before the debate and refreshed before the decision, at execution, and after execution.

By default, each debate and final decision receives all paper-account positions,
the candidate's filled share count, cash, buying power, and open orders with
their requested and filled quantities. Before submitting a trade the pipeline
rechecks positions and open orders, and verifies buys against current cash and
buying power. Changed positions, changed orders, or insufficient funds trigger
a fresh decision, up to three attempts. If required data is unavailable, the candidate stays queued.

A broker-confirmed open order allows the next candidate to proceed. An accepted
after-hours buy adds no shares until it fills. A partial fill appears as owned
shares plus an outstanding order. The queue retains the broker client order ID
until it has saved candidate completion, so restart recovery can finish that
step without submitting a second order.

Use `python -m src.main --candidates data/simen.json --portfolio-source json`
for the original local-ledger decision inputs and order handling. Both modes
trade through Alpaca paper. Broker mode leaves the local ledger untouched.
Reconcile it before switching back to JSON. Run one queue per project copy.

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

At the end of an `--execute-review-all` run, the pipeline replaces `portfolio.json`
with current Alpaca positions. Closed holdings are removed, and an empty account
produces an empty list. Fetch or validation failures preserve the existing file.
The local format supports whole, long positions. Fractional or short positions
raise an error during this sync. An empty-queue rerun also refreshes the file.
