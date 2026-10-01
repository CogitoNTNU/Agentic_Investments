# Agentic Investments

An agent harness for automating investment research using LLM-powered agents with tool access (e.g. fetching financial estimates for stock tickers).

## Setup

```bash
uv sync
```

Create a `.env` file with your API key:

```
IDUN_API_KEY=your-key-here
```

## Usage

```bash
uv run src/main.py
```

## Project structure

- `src/models/` - agent definitions
- `src/tools/` - tools the agents can call
- `src/main.py` - entry point
