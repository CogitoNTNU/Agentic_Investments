"""Process the saved discovery candidates sequentially through paper trading."""

import argparse
import json
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import sleep

# Support both `python src/main.py` and `python -m src.main`.
ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT))


def load_candidates(directory: Path = ROOT / "data" / "news_discovery") -> deque:
    """Read a selected JSON queue, or use the default discovery directory."""
    path = directory
    if directory.is_dir():
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


def research_candidate(candidate: dict) -> dict:
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
    return {
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


def process_candidate(candidate: dict, portfolio_source: str = "alpaca", queue_source: str | None = None) -> dict:
    from src.debate_agent.graph import graph

    ticker = candidate["ticker"]
    packet = research_candidate(candidate)
    print(f"[{ticker}] Starter debatt og beslutningsagent", flush=True)
    return graph.invoke({"ticker": ticker, "analysis_packet": packet, "portfolio_source": portfolio_source, "queue_source": queue_source})


def complete_candidate(ticker: str, source: Path) -> None:
    """Persist progress only after decision and order handling have succeeded."""
    paths = [source]
    if source.is_dir():
        # Keep the preferred file and fallback in sync so completion cannot reappear.
        paths = [source / name for name in ("grouped_candidates.json", "latest_candidates.json")]
    for path in paths:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        data["candidates"] = [
            item for item in data["candidates"]
            if item["ticker"].strip().upper() != ticker.strip().upper()
        ]
        data["total_candidates"] = len(data["candidates"])
        save_json(path, data)


def save_json(path: Path, data: dict) -> None:
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                suffix=".tmp", delete=False) as file:
            temporary = Path(file.name)
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
        for attempt in range(4):
            try:
                temporary.replace(path)
                break
            except PermissionError as error:
                if getattr(error, "winerror", None) not in {5, 32} or attempt == 3:
                    raise
                sleep(0.05 * (attempt + 1))
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def wait_for_replacement_sales(report, execute, output):
    from src.decision_agent.review_execution import report_status
    pending = [ticker for ticker, entry in report["candidates"].items()
               if entry.get("execution", {}).get("state") == "active"]
    if not pending:
        return
    print(f"Waiting for {', '.join(pending)}. Checking Alpaca every 30 seconds.", flush=True)
    while pending:
        sleep(30)
        for ticker in pending.copy():
            execute(report, ticker)
            if report["candidates"][ticker]["execution"]["state"] != "active":
                pending.remove(ticker)
    report["status"] = report_status(report)
    save_json(output, report)


def main(candidate_file: Path | None = None, portfolio_source: str = "alpaca",
         review_portfolio: bool = False, execute_review: str | None = None,
         execute_review_all: bool = False) -> None:
    source = (candidate_file or ROOT / "data" / "news_discovery").resolve()
    output = (source if source.is_dir() else source.parent) / "holdings_review.json"
    previous = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    from src.decision_agent.review_execution import migrate_execution_records, report_status
    migrate_execution_records(previous)
    active = [ticker for ticker, item in previous.get("candidates", {}).items()
              if item.get("execution", {}).get("state") == "active"]
    resume_batch = (execute_review_all and previous.get("mode") == "paper_queue"
                    and previous.get("queue_source") == str(source))
    if review_portfolio and active and previous.get("queue_source") == str(source):
        # Preview the remaining candidates without replacing the paper-order journal.
        output = output.with_name(f"{source.stem}_remaining_review.json")
        previous = {"holdings": previous["holdings"], "as_of": previous["as_of"],
                    "queue_source": str(source), "mode": "review", "status": "holdings_reviewed"}
        active = []
    if active and not (execute_review or resume_batch):
        raise ValueError("Resume the active review execution before processing this queue")
    if review_portfolio or execute_review or execute_review_all:
        from src.decision_agent.review import review_queue
        from src.decision_agent.review_execution import execute_entry, execute_recommendation

        if portfolio_source != "alpaca":
            raise ValueError("Holdings review requires --portfolio-source alpaca")
        if output == source:
            raise ValueError("Review output would overwrite the candidate queue")
        if execute_review:
            execute_recommendation(source, output, execute_review.strip().upper(), save_json,
                                   load_candidates, complete_candidate)
            return
        def execute(report, ticker):
            execute_entry(report, source, output, ticker, save_json, load_candidates, complete_candidate)

        completed = {}
        if resume_batch:
            for ticker in active:
                execute(previous, ticker)
            completed = {t: item for t, item in previous["candidates"].items()
                         if item.get("execution", {}).get("state") not in {None, "needs_review"}}
        queue = load_candidates(source)
        pending = {t for t in active if previous["candidates"][t]["execution"]["state"] == "active"}
        queue = deque(candidate for candidate in queue if candidate["ticker"] not in completed)
        if execute_review_all and not queue and not pending:
            if resume_batch:
                previous["status"] = report_status(previous)
                save_json(output, previous)
            from src.decision_agent.portfolio import sync_from_alpaca
            sync_from_alpaca()
            print("No unevaluated candidates remain. Check the report for order outcomes.")
            return
        report = previous
        while True:
            if queue or not execute_review_all:
                report = review_queue(queue, research_candidate, output, save_json, source,
                                      execute=execute if execute_review_all else None,
                                      completed=completed, previous=report)
            if not execute_review_all:
                break
            wait_for_replacement_sales(report, execute, output)
            # A recovered, pre-debate sale may have filled while polling. Reassess
            # its candidate before allowing any further order for that rotation.
            needs_review = {t for t, item in report["candidates"].items()
                            if item.get("execution", {}).get("state") == "needs_review"}
            if not needs_review:
                break
            queue = deque(c for c in load_candidates(source) if c["ticker"] in needs_review)
            if not queue:
                break
            completed = {t: item for t, item in report["candidates"].items() if t not in needs_review}
        if execute_review_all:
            from src.decision_agent.portfolio import sync_from_alpaca
            sync_from_alpaca()
        print(f"Portfolio review saved to {output}", flush=True)
        return

    from src.decision_agent.trading import sync_pending_order, acknowledge_candidate

    # Resolve any earlier order before starting another candidate.
    print("[Start] Sjekker om tidligere Alpaca-ordrer må avklares", flush=True)
    recovered = sync_pending_order()
    if recovered:
        source = Path(recovered["queue_source"])
        ticker = recovered["decision"]["ticker"]
        complete_candidate(ticker, source)
        acknowledge_candidate(ticker, source)
    source = (candidate_file or ROOT / "data" / "news_discovery").resolve()
    queue = load_candidates(candidate_file) if candidate_file is not None else load_candidates()
    total = len(queue)
    print(f"[Kø] Starter paper trading: {total} kandidater", flush=True)
    while queue:
        candidate = queue[0]
        ticker = candidate["ticker"]
        print(f"[Kø {total - len(queue) + 1}/{total}] Behandler {ticker}", flush=True)
        try:
            result = process_candidate(candidate, portfolio_source, str(source))
        except Exception as error:
            print(f"[{ticker}] Køen stoppet: {type(error).__name__}: {error}", flush=True)
            raise
        print(f"[{ticker}] Ferdig: {json.dumps(result['decision'], ensure_ascii=False)}", flush=True)
        complete_candidate(ticker, source)
        acknowledge_candidate(ticker, source)
        queue.popleft()
        # Release the completed research/debate before starting the next ticker.
        del result, candidate
    print("[Kø] Ferdig. Alle kandidater er behandlet", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a candidate queue through paper trading.")
    parser.add_argument("--candidates", type=Path, help="Candidate JSON file, e.g. data/simen.json")
    parser.add_argument("--portfolio-source", choices=("alpaca", "json"), default="alpaca",
                        help="Source of decision holdings (default: alpaca paper account)")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--execute-review-all", action="store_true",
                       help="Review and paper-trade each queued candidate in order")
    modes.add_argument("--execute-review", metavar="TICKER", help="Paper-trade one saved review recommendation")
    modes.add_argument("--review-portfolio", action="store_true",
                        help="Compare each candidate with current holdings and log recommendations without trading")
    args = parser.parse_args()
    main(args.candidates, args.portfolio_source, args.review_portfolio, args.execute_review, args.execute_review_all)
