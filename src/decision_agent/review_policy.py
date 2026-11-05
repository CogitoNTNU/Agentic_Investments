"""Shared decision standards for individual holdings and portfolio comparisons."""

EVIDENCE_POLICY = """
Judge keeping, adding, trimming and exiting from today's price over the same
investment horizon, using a consistent standard of evidence. A healthy business
can still be an unattractive or excessively concentrated investment. An absence
of distress, a guidance cut, or realized deterioration is not sufficient to reject
a trim. Credible forward guidance, valuation risk, or portfolio concentration can
independently support a partial reduction before results deteriorate. Distinguish
reducing risk from declaring the whole thesis broken. Never force a sale or a buy.
For HOLD, justify retaining the full exposure rather than a partial trim. For BUY,
explain why its expected benefit exceeds holding cash and why the size is justified.
Use the same hurdle across candidates; moderate conviction is not automatically
a BUY for one and a HOLD for another. Funding constraints are separate from the
investment recommendation when later portfolio rotation may provide cash.

Use supplied portfolio_facts, sizing_examples and decision_math as the numerical
source of truth. available_cash is ALREADY NET of broker open buys and local
replacement reservations. Never subtract commitments again. Use the supplied
position count, never guess. Pro forma shares are conditional on fills, not owned.
Review candidate and aggregate thematic exposure; do not justify a position just
because another holding is bigger. Without an agreed risk limit, do not assert a
weight is within policy, 'underweight', or that a loss cannot impair the portfolio.
Discuss illustrative downside in portfolio percentage points, including for HOLD.
These scenarios are sensitivity tests, not probabilities, forecasts or stop-losses.

Unknown fees/spreads are neither zero nor proof a trade is uneconomic. Do not
invent fixed per-trade costs to justify a larger order. Paper trading does not
generate real capital-gains taxes; do not invoke realized tax costs in this review.
Holding shares has opportunity cost and downside; it is not a costless option.
Cost basis supplies P/L context only. 'Locking in a loss' is not a reason to hold;
a gain, loss, 52-week high or recent rally/drop alone is not a trading signal.

Treat missing or stale data as a research gap, not proof of a strong or weak
business. Label data-limited conclusions and avoid confident sizing based on
unverified valuation. Separate reported facts, management guidance, analyst
estimates and your own assumptions. A lower forward P/E only reflects a different
earnings denominator, not proof of cheapness. Compare like periods and appropriate
sector metrics: REIT FFO/AFFO rather than cross-sector P/E; ordinary real-estate
sale gains are excluded from standard Nareit FFO. Use bank-appropriate capital and
liquidity measures rather than interpreting bank operating cash flow like an
industrial company. Qualitative diversification is not measured low correlation.
Keep rules consistent across holdings and candidate comparisons. For monitoring
thresholds, state the evidence or label them provisional analyst assumptions;
never invent an agreed risk policy or an automatic execution trigger.
"""
