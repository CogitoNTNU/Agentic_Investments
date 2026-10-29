import json
from pathlib import Path

from ..nodes import filter_articles, analyze_article


DATA_DIR = Path("data/news_discovery")

TARGET_TICKERS = [
    "EQT",   # Announced merger
    "DASH",  # Reported acquisition talks
    "META",  # Financing and analyst opinion
    "CNC",   # Conflicting earnings coverage
    "SHW",   # Earnings coverage
    "AVGO",  # Mixed news
]


def main():

    raw = json.loads(
        (DATA_DIR / "marketaux_raw_articles.json")
        .read_text(encoding="utf-8")
    )

    old_data = json.loads(
        (DATA_DIR / "latest_candidates.json")
        .read_text(encoding="utf-8")
    )

    articles = filter_articles({
        "raw_articles": raw
    })["articles"]

    # Limit to two articles per ticker
    selected = []

    for ticker in TARGET_TICKERS:
        matches = [
            article
            for article in articles
            if article["ticker"] == ticker
        ]
        selected.extend(matches[:2])

    if not selected:
        print("No matching cached articles.")
        return

    print(f"\nTesting {len(selected)} article-ticker pairs")

    # Uses LLM, but not Marketaux
    new_events = analyze_article({
        "articles": selected
    })["events"]

    # Index previous confidence scores for comparison
    old_scores = {}

    for candidate in old_data["candidates"]:
        for event in candidate.get("events", []):
            key = (
                event["source_uuid"],
                event["ticker"],
                event["event_type"],
            )
            old_scores.setdefault(key, []).append(
                event["confidence"]
            )

    print("\n=== CONFIDENCE COMPARISON ===")

    for event in new_events:

        key = (
            event["source_uuid"],
            event["ticker"],
            event["event_type"],
        )

        previous = old_scores.get(key, [])

        print(
            f"\n{event['ticker']} | "
            f"{event['event_type']}"
        )

        print("Old confidence:", previous or "Not matched")
        print("New confidence:", event["confidence"])
        print("Company:", event["primary_company"])
        print("Relationship:", event["ticker_relationship"])
        print("Summary:", event["summary"])

    output = DATA_DIR / "confidence_targeted_preview.json"

    output.write_text(
        json.dumps(
            {
                "articles": selected,
                "events": new_events,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"\nSaved: {output}")


if __name__ == "__main__":
    main()