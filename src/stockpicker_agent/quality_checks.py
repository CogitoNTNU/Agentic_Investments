"""Conservative, deterministic quality flags for grouped news events.

No API requests or model calls. A conflict flag is a review request,
not proof that either article is wrong.
"""

import re
from typing import Any

_METRIC = r"(?:eps|earnings?|profits?|results?)"
_EXPECTATION = r"(?:analyst\s+)?(?:estimates?|expectations?|consensus|forecasts?)"
_POSITIVE = r"(?:beat(?:s|en|ing)?|exceed(?:s|ed|ing)?|surpass(?:es|ed|ing)?|above|topp?(?:ed|ing|s)?)"
_NEGATIVE = r"(?:miss(?:es|ed|ing)?|fell\s+short|falls?\s+short|below)"

_POSITIVE_PATTERN = re.compile(
    rf"\b{_METRIC}\b.{{0,130}}\b{_POSITIVE}\b.{{0,80}}\b{_EXPECTATION}\b",
    re.IGNORECASE | re.DOTALL,
)
_NEGATIVE_PATTERN = re.compile(
    rf"\b{_METRIC}\b.{{0,130}}\b{_NEGATIVE}\b.{{0,80}}\b{_EXPECTATION}\b",
    re.IGNORECASE | re.DOTALL,
)
_SIMPLE_POSITIVE = re.compile(r"\b(?:earnings?|eps)\s+beats?\b", re.IGNORECASE)
_SIMPLE_NEGATIVE = re.compile(r"\b(?:earnings?|eps)\s+miss(?:es|ed)?\b", re.IGNORECASE)


def _surprise_signal(source: dict[str, Any]) -> str | None:
    """Classify unambiguous article-level earnings-surprise language."""
    text = (
        f"{source.get('headline') or ''}. "
        f"{source.get('summary') or ''}"
    )
    positive = bool(_POSITIVE_PATTERN.search(text) or _SIMPLE_POSITIVE.search(text))
    negative = bool(_NEGATIVE_PATTERN.search(text) or _SIMPLE_NEGATIVE.search(text))
    if positive and not negative:
        return "beat"
    if negative and not positive:
        return "miss"
    return None  # mixed or no clear characterization


def flag_conflicting_earnings(group: dict[str, Any]) -> dict[str, Any]:
    """Flag clear cross-source beat-vs-miss disagreements for manual review.

    This is deliberately narrow and cannot independently verify accounting
    basis, estimate providers, or numerical correctness.
    """
    result = dict(group)
    result["needs_verification"] = False
    result["verification_reason"] = None
    result["conflicting_source_uuids"] = []

    if "earnings" not in group.get("event_types", []):
        return result

    signals: dict[str, set[str]] = {"beat": set(), "miss": set()}
    for source in group.get("sources", []):
        # An earnings report may be extracted as a market_move event
        # when the article focuses on the share-price reaction.
        # For an earnings group, inspect every source for an explicit
        # beat/miss characterization rather than checking event_type.
        source_id = source.get("source_uuid")
        if not source_id:
            continue
        signal = _surprise_signal(source)
        if signal is not None:
            signals[signal].add(source_id)

    if signals["beat"] and signals["miss"]:
        # Require at least two distinct source articles.
        source_ids = signals["beat"] | signals["miss"]
        if len(source_ids) >= 2:
            result["needs_verification"] = True
            result["verification_reason"] = (
                "Sources disagree on whether earnings/EPS beat or missed "
                "expectations. Verify GAAP vs adjusted metrics and the "
                "consensus estimate before resolving."
            )
            result["conflicting_source_uuids"] = sorted(source_ids)

    return result
