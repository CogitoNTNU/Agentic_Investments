"""Audit previous Stockpicker JSON outputs without any API or LLM calls.

Run from the repository root:
    uv run python -m src.stockpicker_agent.audit_cached

This does not replace rerunning the graph after prompt/schema changes.
"""

import argparse
import json
from pathlib import Path

from .quality_checks import flag_conflicting_earnings


def audit(candidates_file: Path, grouped_file: Path, output_file: Path) -> None:
    candidates_data = json.loads(candidates_file.read_text(encoding="utf-8"))
    grouped_data = json.loads(grouped_file.read_text(encoding="utf-8"))

    candidate_events = [
        event
        for candidate in candidates_data.get("candidates", [])
        for event in candidate.get("events", [])
    ]
    nonqualifying = [
        event for event in candidate_events
        if not event.get("qualifies_for_investigation", False)
    ]
    perfect_confidence = [
        event for event in candidate_events
        if event.get("confidence") == 1.0
    ]

    flagged_tickers = []
    preview_candidates = []
    for candidate in grouped_data.get("candidates", []):
        qualifying_groups = []
        context_groups = []
        for group in candidate.get("event_groups", []):
            checked = flag_conflicting_earnings(group)
            qualifies = any(
                source.get("qualifies_for_investigation") is True
                for source in checked.get("sources", [])
            )
            checked["qualifies_for_investigation"] = qualifies
            if checked["needs_verification"]:
                flagged_tickers.append(candidate["ticker"])
            if qualifies:
                qualifying_groups.append(checked)
            else:
                context_groups.append(checked)

        preview_candidates.append({
            **candidate,
            "event_groups": qualifying_groups,
            "context_event_groups": context_groups,
            "unique_event_count": len(qualifying_groups),
            "context_unique_event_count": len(context_groups),
        })

    preview = {**grouped_data, "candidates": preview_candidates}
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(preview, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n=== CACHED STOCKPICKER AUDIT (NO API CALLS) ===")
    print(f"Candidates: {len(candidates_data.get('candidates', []))}")
    print(f"Candidate-level events: {len(candidate_events)}")
    print(f"Non-qualifying events: {len(nonqualifying)}")
    print(f"Events with confidence = 1.0: {len(perfect_confidence)}")
    print("\nNon-qualifying supporting events:")
    for event in nonqualifying:
        print(f"  {event['ticker']}: {event['event_type']}")
    print("\nPossible earnings reporting conflicts:")
    if flagged_tickers:
        for ticker in sorted(set(flagged_tickers)):
            print(f"  {ticker}: needs verification")
    else:
        print("  None detected by conservative text patterns")
    print(f"\nAudit preview saved: {output_file}")
    print(
        "Note: This audit does not re-evaluate company attribution "
        "or recalibrate confidence."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("data/news_discovery/latest_candidates.json"),
    )
    parser.add_argument(
        "--grouped",
        type=Path,
        default=Path("data/news_discovery/grouped_candidates.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/news_discovery/grouped_candidates_quality_preview.json"),
    )
    args = parser.parse_args()
    audit(args.candidates, args.grouped, args.output)
