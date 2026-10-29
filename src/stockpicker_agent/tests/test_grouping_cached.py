"""Rerun only event grouping + conflict detection using saved candidates.

No Marketaux requests and no article-analysis calls. Grouping may call the LLM.
Run: uv run python -m src.stockpicker_agent.test_grouping_cached
"""
import argparse
import json
from pathlib import Path

from ..nodes import group_events


TARGET_TICKERS = {"CNC", "PNR", "SHW"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidates", type=Path,
        default=Path("data/news_discovery/latest_candidates.json"),
    )
    args = parser.parse_args()
    path = args.candidates
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"Reading: {path}")
    selected = [
        item for item in data.get("candidates", [])
        if item.get("ticker") in TARGET_TICKERS
    ]
    print(f"Grouping {len(selected)} cached candidates (no article analysis)")
    if not selected:
        print("No matching candidates in saved JSON")
        return

    result = group_events({"candidates": selected})
    grouped = result["grouped_candidates"]

    for candidate in grouped:
        print(f"\n{candidate['ticker']}:")
        for group in candidate.get("event_groups", []):
            print("  Event types:", group.get("event_types"))
            print("  Sources:", group.get("source_count"))
            print("  Needs verification:", group.get("needs_verification", False))
            print("  Reason:", group.get("verification_reason"))

    out = Path("data/news_discovery/targeted_grouping_preview.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"candidates": grouped}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nSaved: {out}")
    print("Note: Results reflect the candidate file selected above.")


if __name__ == "__main__":
    main()
