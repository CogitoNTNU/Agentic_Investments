import json
from pathlib import Path

from .event_dedup import group_candidate_events


path = Path("data/news_discovery/latest_candidates.json")

with path.open(encoding="utf-8") as file:
    data = json.load(file)


grouped_candidates = []

for candidate in data["candidates"]:

    result = group_candidate_events(candidate)
    grouped_candidates.append(result)

    print(f"\nTicker: {result['ticker']}")
    print(f"News records: {result['event_count']}")
    print(f"Unique events: {result['unique_event_count']}")

    for group in result["event_groups"]:
        print(f"  - {group['summary']}")
        print(f"    Sources: {group['source_count']}")


# Save grouped candidates separately
output_path = Path(
    "data/news_discovery/grouped_candidates.json"
)

output_path.write_text(
    json.dumps(
        {
            "total_candidates": len(grouped_candidates),
            "candidates": grouped_candidates,
        },
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)

print(f"\nSaved to {output_path}")