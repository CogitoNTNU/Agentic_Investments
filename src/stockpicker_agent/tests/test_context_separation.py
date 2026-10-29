"""Offline integration test for Stockpicker candidate/context separation.

Run from the project root:
    uv run python -m src.stockpicker_agent.test_context_separation

Uses synthetic data, no Marketaux requests, and no LLM calls.
The event-grouping model is mocked, while the project's real
select_candidates() and group_events() functions are tested.
"""

from unittest.mock import patch

from .. import event_dedup
from ..event_dedup import EventGroup, EventGrouping
from ..nodes import group_events, select_candidates


def article(source_uuid: str, ticker: str) -> dict:
    return {
        "source_uuid": source_uuid,
        "ticker": ticker,
        "title": f"Synthetic article {source_uuid}",
        "url": f"https://example.com/{source_uuid}",
        "published_at": "2026-10-27T12:00:00Z",
    }


def event(
    source_uuid: str,
    ticker: str,
    relationship: str,
    event_type: str,
    materiality: float,
    confidence: float,
    investigate: bool,
) -> dict:
    return {
        "source_uuid": source_uuid,
        "ticker": ticker,
        "primary_company": "Synthetic Company",
        "ticker_relationship": relationship,
        "event_type": event_type,
        "summary": f"Synthetic {event_type} event: {source_uuid}",
        "sentiment": 0.0,
        "materiality": materiality,
        "novelty": 5.0,
        "confidence": confidence,
        "investigate": investigate,
    }


def main() -> None:
    # The only event allowed to determine META's selection and priority.
    qualifying_id = "meta-financing"

    # These may be relevant context but must NOT affect the priority score.
    low_impact_id = "meta-analyst"
    indirect_id = "meta-indirect"

    # This event is unrelated and must be excluded entirely.
    unrelated_id = "meta-unrelated"

    # An indirect-only ticker must not become a candidate.
    indirect_only_id = "avgo-indirect"

    articles = [
        article(qualifying_id, "META"),
        article(low_impact_id, "META"),
        article(indirect_id, "META"),
        article(unrelated_id, "META"),
        article(indirect_only_id, "AVGO"),
    ]
    events = [
        event(qualifying_id, "META", "direct", "financing", 7, 0.9, True),
        event(low_impact_id, "META", "direct", "analyst_rating", 2, 1.0, False),
        event(indirect_id, "META", "indirect", "other", 9, 1.0, True),
        event(unrelated_id, "META", "unrelated", "earnings", 10, 1.0, True),
        event(indirect_only_id, "AVGO", "indirect", "merger_acquisition", 10, 1.0, True),
    ]

    print("=== TEST 1: CANDIDATE SELECTION (OFFLINE) ===")
    candidates = select_candidates({"articles": articles, "events": events})[
        "candidates"
    ]

    assert len(candidates) == 1, f"Expected only META, got {candidates}"
    candidate = candidates[0]
    assert candidate["ticker"] == "META"

    qualifying_ids = {e["source_uuid"] for e in candidate["events"]}
    context_ids = {e["source_uuid"] for e in candidate["context_events"]}
    assert qualifying_ids == {qualifying_id}, qualifying_ids
    assert context_ids == {low_impact_id, indirect_id}, context_ids
    assert unrelated_id not in qualifying_ids | context_ids
    assert candidate["event_count"] == 1
    assert candidate["context_event_count"] == 2

    # The qualifying event alone determines the priority score.
    expected_priority = round(7 * 0.75 + 0.9 * 10 * 0.25, 2)
    assert candidate["priority_score"] == expected_priority

    print(f"Candidate: {candidate['ticker']}")
    print(f"Priority (qualifying event only): {candidate['priority_score']}")
    print(f"Qualifying events: {sorted(qualifying_ids)}")
    print(f"Context events: {sorted(context_ids)}")
    print("Unrelated event excluded: PASS")
    print("Indirect-only ticker excluded: PASS")

    print("\n=== TEST 2: FINAL GROUPED OUTPUT (MOCKED LLM) ===")

    # The real group_events() builds input as qualifying events first,
    # followed by context events. Mock only the grouping model's answer.
    # No network or LLM request can occur in this test.
    fake_grouping = EventGrouping(
        groups=[
            EventGroup(event_ids=[0], summary="Qualifying financing event"),
            EventGroup(event_ids=[1], summary="Context-only analyst opinion"),
            EventGroup(event_ids=[2], summary="Indirect context event"),
        ]
    )
    with patch.object(event_dedup, "structured_llm") as mocked_model:
        mocked_model.invoke.return_value = fake_grouping
        grouped_candidates = group_events({"candidates": candidates})[
            "grouped_candidates"
        ]
        mocked_model.invoke.assert_called_once()

    assert len(grouped_candidates) == 1
    grouped = grouped_candidates[0]
    assert grouped["event_count"] == 1
    assert grouped["context_event_count"] == 2
    assert grouped["unique_event_count"] == 1
    assert grouped["context_unique_event_count"] == 2
    assert len(grouped["event_groups"]) == 1
    assert len(grouped["context_event_groups"]) == 2
    assert grouped["priority_score"] == expected_priority

    qualifying_group = grouped["event_groups"][0]
    assert qualifying_group["qualifies_for_investigation"] is True
    assert qualifying_group["sources"][0]["source_uuid"] == qualifying_id

    context_group_ids = {
        source["source_uuid"]
        for group in grouped["context_event_groups"]
        for source in group["sources"]
    }
    assert context_group_ids == {low_impact_id, indirect_id}
    assert all(
        group["qualifies_for_investigation"] is False
        for group in grouped["context_event_groups"]
    )

    print(f"Qualifying event groups: {grouped['unique_event_count']}")
    print(f"Context-only groups: {grouped['context_unique_event_count']}")
    print("Priority unchanged after grouping: PASS")
    print("\nALL TESTS PASSED — no Marketaux requests or LLM calls")


if __name__ == "__main__":
    main()
