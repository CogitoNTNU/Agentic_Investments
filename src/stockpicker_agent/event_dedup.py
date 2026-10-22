import json

from pydantic import BaseModel, Field
from ..model import get_model


class EventGroup(BaseModel):
    event_ids: list[int] = Field(min_length=1)
    summary: str


class EventGrouping(BaseModel):
    groups: list[EventGroup]


llm = get_model()
structured_llm = llm.with_structured_output(EventGrouping)


SYSTEM_PROMPT = """
You are a financial news event deduplication system.

Your task is to identify which news records describe
the same underlying real-world financial event.

Rules:
- Only group records that describe the same actual event.
- Two articles about the same quarterly earnings
  report should belong to one group.
- Different quarterly reports are different events.
- Different corporate actions are different events.
- Do not group articles solely because they have
  the same ticker or event_type.
- Do not group separate events just because they
  happened on the same day.
- Preserve every input event ID exactly once.
- Do not invent events or event IDs.
- Write one short, factual summary per group.
- Only use information contained in the input.
"""


def group_candidate_events(candidate: dict) -> dict:

    events = candidate.get("events", [])

    if not events:
        return {
            "ticker": candidate["ticker"],
            "priority_score": candidate["priority_score"],
            "event_count": 0,
            "unique_event_count": 0,
            "event_groups": [],
        }

    # Each event gets a unique temporary ID
    numbered_events = [
        {
            "event_id": i,
            "event_type": event["event_type"],
            "summary": event["summary"],
            "headline": event.get("headline", ""),
            "published_at": event.get("published_at"),
        }
        for i, event in enumerate(events)
    ]

    # No LLM call needed for a single event
    if len(events) == 1:
        groups = [
            EventGroup(
                event_ids=[0],
                summary=events[0]["summary"],
            )
        ]
    else:
        result = structured_llm.invoke([
            ("system", SYSTEM_PROMPT),
            ("human", json.dumps(numbered_events)),
        ])

        groups = result.groups

    # Validate that every input event appears exactly once
    all_ids = [
        event_id
        for group in groups
        for event_id in group.event_ids
    ]

    if (
        len(all_ids) != len(events)
        or set(all_ids) != set(range(len(events)))
    ):
        raise ValueError(
            "Invalid event grouping: missing or duplicate IDs"
        )

    event_groups = []

    for group in groups:

        grouped_events = [
            events[i]
            for i in group.event_ids
        ]

        sources = []

        for event in grouped_events:

            sources.append({
                "source_uuid": event["source_uuid"],
                "headline": event.get("headline"),
                "source_url": event.get("source_url"),
                "published_at": event.get("published_at"),
                "qualifies_for_investigation": event.get(
                    "qualifies_for_investigation",
                    (
                        event.get("investigate", False)
                        and event.get("materiality", 0) >= 4
                        and event.get("confidence", 0) >= 0.65
                    )
                ),

                # Original event information
                "event_type": event["event_type"],
                "summary": event["summary"],
                "sentiment": event["sentiment"],
                "materiality": event["materiality"],
                "novelty": event["novelty"],
                "confidence": event["confidence"],
                "investigate": event["investigate"],
            })

        # Count distinct source articles
        source_count = len({
            source["source_uuid"]
            for source in sources
        })

        event_groups.append({
            "summary": group.summary,

            "event_types": list(dict.fromkeys(
                event["event_type"]
                for event in grouped_events
            )),

            "source_count": source_count,
            "sources": sources,
        })

    # Return a clean candidate structure
    return {
        "ticker": candidate["ticker"],
        "priority_score": candidate["priority_score"],

        "event_count": len(events),
        "unique_event_count": len(event_groups),

        "event_groups": event_groups,
    }