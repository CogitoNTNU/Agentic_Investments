import json
from pathlib import Path

from ..nodes import (
    filter_articles,
    analyze_article,
    select_candidates,
    group_events,
)


def main():

    cache_path = Path(
        "data/news_discovery/marketaux_raw_articles.json"
    )

    raw_articles = json.loads(
        cache_path.read_text(encoding="utf-8")
    )

    filtered = filter_articles({
        "raw_articles": raw_articles
    })["articles"]

    # Only test the two problematic tickers
    target_tickers = {"CNC", "PNR", "SHW"}

    selected = [
        article
        for article in filtered
        if article["ticker"] in target_tickers
    ]

    print(f"\nTesting {len(selected)} article-ticker pairs")

    if not selected:
        print("No matching articles found.")
        return

    events = analyze_article({
        "articles": selected
    })["events"]

    print("\n=== ATTRIBUTION RESULTS ===")

    for event in events:
        print(
            f"Ticker: {event['ticker']} | "
            f"Primary: {event['primary_company']} | "
            f"Relationship: {event['ticker_relationship']} | "
            f"Investigate: {event['investigate']}"
        )

    candidates = select_candidates({
        "articles": selected,
        "events": events,
    })["candidates"]

    print("\n=== QUALIFIED CANDIDATES ===")

    for candidate in candidates:
        print(
            candidate["ticker"],
            "| Priority:",
            candidate["priority_score"],
        )

    grouped = group_events({
        "candidates": candidates
    })["grouped_candidates"]

    print("\n=== EARNINGS CONFLICT CHECK ===")

    for candidate in grouped:
        print(f"\nTicker: {candidate['ticker']}")

        for group in candidate.get("event_groups", []):

            print(
                "Event types:",
                group.get("event_types")
            )

            print(
                "Needs verification:",
                group.get("needs_verification", False)
            )


if __name__ == "__main__":
    main()