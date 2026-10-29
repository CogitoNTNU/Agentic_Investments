import json
from pathlib import Path
from datetime import datetime, timezone

from ..graph import graph


result = graph.invoke({})

print("\n=== DEBUG ===")
print("Raw articles:", len(result["raw_articles"]))
print("Filtered articles:", len(result["articles"]))
print("Events:", len(result["events"]))
print("Candidates:", len(result["candidates"]))

for event in result["events"]:
    print(
        event["ticker"],
        "|", event["event_type"],
        "| materiality:", event["materiality"],
        "| confidence:", event["confidence"],
        "| investigate:", event["investigate"]
    )


# ----------------------------------
# Save original candidates
# ----------------------------------

now = datetime.now(timezone.utc)

output = {
    "generated_at": now.isoformat(),
    "total_candidates": len(result["candidates"]),
    "candidates": result["candidates"]
}

output_dir = Path("data/news_discovery")
output_dir.mkdir(parents=True, exist_ok=True)

latest_path = output_dir / "latest_candidates.json"

history_dir = output_dir / "history"
history_dir.mkdir(parents=True, exist_ok=True)

history_path = history_dir / (
    now.strftime("%Y%m%d_%H%M%S") + ".json"
)

json_data = json.dumps(
    output,
    indent=2,
    ensure_ascii=False
)

latest_path.write_text(json_data, encoding="utf-8")
history_path.write_text(json_data, encoding="utf-8")

print(f"Saved {len(result['candidates'])} candidates")
print(f"File: {latest_path}")




grouped_output = {
    "generated_at": now.isoformat(),
    "total_candidates": len(result["grouped_candidates"]),
    "candidates": result["grouped_candidates"],
}

grouped_json_data = json.dumps(
    grouped_output,
    indent=2,
    ensure_ascii=False
)

grouped_path = output_dir / "grouped_candidates.json"

grouped_path.write_text(
    grouped_json_data,
    encoding="utf-8"
)

grouped_history_dir = history_dir / "grouped"

grouped_history_dir.mkdir(
    parents=True,
    exist_ok=True
)

grouped_history_path = (
    grouped_history_dir / history_path.name
)

grouped_history_path.write_text(
    grouped_json_data,
    encoding="utf-8"
)

print(f"Grouped file: {grouped_path}")
print(f"Grouped history: {grouped_history_path}")