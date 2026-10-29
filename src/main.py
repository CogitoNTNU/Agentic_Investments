"""Process the saved discovery candidates sequentially through paper trading."""

import json
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

# Support both `python src/main.py` and `python -m src.main`.
ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT))


def load_candidates(directory: Path = ROOT / "data" / "news_discovery") -> deque:
    """Prefer grouped discovery data; fall back to the latest raw candidates."""
    path = directory / "grouped_candidates.json"
    if not path.exists():
        path = directory / "latest_candidates.json"
    print(f"[Kø] Leser kandidater fra {path}", flush=True)
    candidates = json.loads(path.read_text(encoding="utf-8"))["candidates"]
    queue = deque()
    seen = set()
    for candidate in candidates:
        ticker = candidate["ticker"].strip().upper()
        if not ticker:
            raise ValueError("Candidate ticker must not be blank")
        if ticker not in seen:
            queue.append({**candidate, "ticker": ticker})
            seen.add(ticker)
    return queue


def process_candidate(candidate: dict) -> dict:
    from src.debate_agent.graph import graph
    from src.supervisor.research import gather_research_data

    ticker = candidate["ticker"]
    print(f"[{ticker}] Starter research: nyheter, rapportanalyse og finansdata", flush=True)
    research = json.loads(gather_research_data.invoke({"ticker": ticker}))
    print(f"[{ticker}] Research ferdig. Bygger analysegrunnlag", flush=True)
    as_of = datetime.now(timezone.utc).date().isoformat()
    # Keep the complete source outputs as evidence, without another LLM rewrite.
    sources = {
        "discovery": candidate,
        **{
            source: research[source]
            for source in ("news_agent", "economic_agent", "finance_agent")
        },
    }
    packet = {
        "ticker": ticker,
        "company_name": candidate.get("primary_company") or ticker,
        "as_of": as_of,
        "time_horizon": "6-12 months",
        "evidence": [
            {
                "id": source,
                "category": "research",
                "statement": json.dumps(data, ensure_ascii=False, default=str),
                "source": source,
                "as_of": as_of,
            }
            for source, data in sources.items()
        ],
    }
    print(f"[{ticker}] Starter debatt og beslutningsagent", flush=True)
    return graph.invoke({"ticker": ticker, "analysis_packet": packet})


def main() -> None:
    from src.decision_agent.trading import sync_pending_order

    # Resolve any earlier order before starting another candidate.
    print("[Start] Sjekker om tidligere Alpaca-ordrer må avklares", flush=True)
    sync_pending_order()
    queue = load_candidates()
    total = len(queue)
    print(f"[Kø] Starter paper trading: {total} kandidater", flush=True)
    while queue:
        candidate = queue[0]
        ticker = candidate["ticker"]
        print(f"[Kø {total - len(queue) + 1}/{total}] Behandler {ticker}", flush=True)
        try:
            result = process_candidate(candidate)
        except Exception as error:
            print(f"[{ticker}] Køen stoppet: {type(error).__name__}: {error}", flush=True)
            raise
        print(f"[{ticker}] Ferdig: {json.dumps(result['decision'], ensure_ascii=False)}", flush=True)
        queue.popleft()
    print("[Kø] Ferdig. Alle kandidater er behandlet", flush=True)


if __name__ == "__main__":
    main()
