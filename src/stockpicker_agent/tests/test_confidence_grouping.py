import json
from pathlib import Path

from ..nodes import select_candidates, group_events


DATA_DIR = Path("data/news_discovery")


def main():

    input_path = (
        DATA_DIR / "confidence_targeted_preview.json"
    )

    data = json.loads(
        input_path.read_text(encoding="utf-8")
    )

    # Step 1: Candidate selection
    candidates = select_candidates({
        "articles": data["articles"],
        "events": data["events"],
    })["candidates"]

    print("\n=== SELECTED CANDIDATES ===")

    for candidate in candidates:
        print(
            candidate["ticker"],
            "| Priority:",
            candidate["priority_score"],
            "| Qualifying:",
            len(candidate.get("events", [])),
            "| Context:",
            len(candidate.get("context_events", [])),
        )

    # Step 2: Event grouping and quality checks
    grouped = group_events({
        "candidates": candidates
    })["grouped_candidates"]

    print("\n=== GROUPING RESULTS ===")

    for candidate in grouped:

        print(f"\nTicker: {candidate['ticker']}")

        for group in candidate.get("event_groups", []):

            print("Types:", group["event_types"])
            print(
                "Needs verification:",
                group.get("needs_verification", False),
            )
            print(
                "Reason:",
                group.get("verification_reason"),
            )

    output = (
        DATA_DIR / "confidence_grouping_preview.json"
    )

    output.write_text(
        json.dumps(
            {"grouped_candidates": grouped},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"\nSaved: {output}")


if __name__ == "__main__":
    main()