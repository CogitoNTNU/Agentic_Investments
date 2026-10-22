from .event_dedup import group_candidate_events


def make_event(
    source_uuid,
    event_type,
    summary,
    published_at="2026-10-21T12:00:00Z",
):
    return {
        "source_uuid": source_uuid,
        "ticker": "TEST",
        "event_type": event_type,
        "summary": summary,
        "headline": summary,
        "source_url": f"https://example.com/{source_uuid}",
        "published_at": published_at,
        "sentiment": 0.2,
        "materiality": 7.0,
        "novelty": 5.0,
        "confidence": 0.8,
        "investigate": True,
        "qualifies_for_investigation": True,
    }


cases = [
    (
        "TEST 1: Same earnings event",
        [
            make_event(
                "a1", "earnings",
                "Example Corp reported record revenue in Q3 2026."
            ),
            make_event(
                "a2", "earnings",
                "Example Corp Q3 2026 earnings showed record sales."
            ),
        ],
        [{"a1", "a2"}],
    ),
    (
        "TEST 2: Different quarters",
        [
            make_event(
                "b1", "earnings",
                "Example Corp reported Q2 2026 earnings in July."
            ),
            make_event(
                "b2", "earnings",
                "Example Corp reported Q3 2026 earnings in October."
            ),
        ],
        [{"b1"}, {"b2"}],
    ),
    (
        "TEST 3: Earnings and acquisition",
        [
            make_event(
                "c1", "earnings",
                "Example Corp reported its Q3 2026 earnings."
            ),
            make_event(
                "c2", "merger_acquisition",
                "Example Corp announced the acquisition of "
                "Another Company in October 2026."
            ),
        ],
        [{"c1"}, {"c2"}],
    ),
    (
        "TEST 4: Duplicate earnings plus regulatory event",
        [
            make_event(
                "d1", "earnings",
                "Example Corp released its Q3 2026 results."
            ),
            make_event(
                "d2", "earnings",
                "Example Corp reported Q3 2026 revenue and profit."
            ),
            make_event(
                "d3", "regulatory",
                "Example Corp faces a separate regulatory "
                "investigation announced in October 2026."
            ),
        ],
        [{"d1", "d2"}, {"d3"}],
    ),
    (
        "TEST 5: Single event",
        [
            make_event(
                "e1", "major_contract",
                "Example Corp signed a major new contract."
            ),
        ],
        [{"e1"}],
    ),
    (
        "TEST 6: No events",
        [],
        [],
    ),
]


for name, events, expected_groups in cases:

    candidate = {
        "ticker": "TEST",
        "priority_score": 7.25,
        "events": events,
    }

    result = group_candidate_events(candidate)

    actual_groups = {
        frozenset(
            source["source_uuid"]
            for source in group["sources"]
        )
        for group in result["event_groups"]
    }

    expected = {
        frozenset(group)
        for group in expected_groups
    }

    passed = actual_groups == expected

    print(f"\n{name}")
    print(f"News records: {result['event_count']}")
    print(f"Unique events: {result['unique_event_count']}")

    for group in result["event_groups"]:
        print(f"  - {group['summary']}")
        print(
            "    Source IDs:",
            [
                source["source_uuid"]
                for source in group["sources"]
            ]
        )

    print("PASS" if passed else "FAIL")

    if not passed:
        print("Expected:", expected_groups)
        print("Actual:", actual_groups)