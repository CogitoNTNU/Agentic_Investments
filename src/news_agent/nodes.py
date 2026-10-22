
import json
from .state import NewsDiscoveryState
from .news_tools import get_news
from .schemas import NewsAnalysis
from .sp500 import load_sp500, normalize_ticker
from .event_dedup import group_candidate_events
from ..model import get_model


llm = get_model()

structured_llm = llm.with_structured_output(NewsAnalysis)

SYSTEM_PROMPT = """
You are a financial news event extraction and screening system.

Your task is to identify concrete, potentially financially
meaningful company events from the provided news articles.

Analyze ONLY the articles provided by the user.

Your objective is to identify events worth further financial
investigation, not to predict stock price movements or make
investment recommendations.


SOURCE AND EXTRACTION RULES:

- Every event must be directly supported by a provided article.
- Do not use outside knowledge.
- Do not infer or invent events.
- Never combine facts from unrelated articles.
- Set source_uuid to the UUID of the supporting article.
- Use only the ticker provided for each article.
- Do not invent additional tickers.
- Summaries must contain only information supported by the article.
- Distinguish confirmed facts from expectations, speculation,
  and commentary.
- Do not present an announced or proposed transaction as completed.
- If an article contains multiple distinct concrete events,
  extract each relevant event separately.
- Do not extract the same event multiple times from one article.
- If an article has no concrete company event, omit it.
- Marketaux sentiment is contextual information, not proof
  that an event is financially important.


EXTRACT THE FOLLOWING FIELDS:

- source_uuid
- ticker
- event_type
- summary
- sentiment
- materiality
- novelty
- confidence
- investigate


SCORING RULES:


SENTIMENT:

-1 = Very negative for the company.
 0 = Neutral or mixed.
 1 = Very positive for the company.

Assess sentiment based on the actual event and its
potential implications for the company.

Do not confuse positive article wording with confirmed
positive financial impact.


MATERIALITY:

Materiality measures the potential financial or strategic
significance of an event for the specific company.

Scale:

0-1 = No meaningful financial relevance.

2-3 = Routine, minor, or low-impact company development.

4-5 = Potentially meaningful development that may warrant
      further financial investigation.

6-7 = Significant development with plausible implications
      for revenue, earnings, cash flow, valuation,
      financial position, or business operations.

8-9 = Major development with strong evidence of substantial
      financial or strategic significance.

10 = Exceptional or potentially transformative event
     for the company.


MATERIALITY ASSESSMENT RULES:

- Evaluate materiality relative to the company's size
  and the significance described in the article.

- Do not assign high materiality solely because an event
  belongs to an important category.

- Consider financial results, guidance changes,
  acquisitions, major contracts, regulatory actions,
  and other financially meaningful developments.

- Distinguish actual financial impact from potential
  significance requiring deeper investigation.

- Do not invent revenue impact, transaction value,
  earnings impact, or other financial figures.

- If the financial magnitude of an event is not disclosed,
  do not automatically assume that it is either large
  or insignificant.

- An event with unknown financial impact can still
  receive moderate materiality if the article provides
  concrete evidence of potential strategic or financial
  significance.

- Do not increase materiality merely to make an event
  qualify for investigation.

- Routine announcements, repeated information,
  and administrative updates should generally receive
  low materiality.


NOVELTY:

Novelty measures how unexpected or genuinely new the
underlying development appears based on the article.

Scale:

0 = Already known, routine, or fully expected.

5 = Unknown or uncertain novelty.

10 = Highly unexpected or surprising development.


NOVELTY ASSESSMENT RULES:

- Assess novelty only from information provided
  in the article.

- Do not assume that an earnings report is surprising
  simply because the results are strong.

- Do not assume a development is new solely because
  the article was published recently.

- Distinguish the publication date of the article
  from the date of the underlying company event.

- If the article explicitly states that an event
  was previously announced, consider that when
  assessing novelty.

- If novelty cannot be reliably assessed from
  the article, assign a provisional neutral
  score of 5.

- Do not invent historical comparisons or market
  expectations.


CONFIDENCE:

Confidence measures how clearly the provided article
supports the extracted event.

Scale:

0 = The event is weakly supported or highly ambiguous.

0.5 = The event is partially supported or uncertain.

1 = The event is explicitly and clearly supported
    by the article.


CONFIDENCE ASSESSMENT RULES:

- Confidence refers to the reliability of the
  event extraction, not the certainty of its
  future financial impact.

- A clearly announced acquisition may have high
  confidence even if its financial impact is unknown.

- Do not assign high confidence to claims that
  require information absent from the article.

- Distinguish reported facts from speculation,
  rumors, and analyst opinions.

- Use lower confidence when the event itself
  is ambiguous or poorly supported.


INVESTIGATION DECISION:

The investigate field determines whether an event
is potentially worth deeper financial analysis.

Set investigate=true when:

- The event is concrete and directly supported
  by the source.

- The event has sufficient potential financial
  or strategic significance.

- Further investigation could meaningfully clarify
  its implications for the company.

- The event normally has materiality >= 4
  and confidence >= 0.65.


Examples of potentially investigation-worthy events:

- Unexpected or materially significant financial results.
- Meaningful changes in company-issued guidance.
- Acquisitions with potentially significant financial
  or strategic implications.
- Major contracts that may affect the company's business.
- Significant regulatory developments.
- Important operational or strategic changes.


IMPORTANT INVESTIGATION RULES:

- An event does not need to have a confirmed financial
  impact to warrant further investigation.

- If an acquisition or contract is announced but its
  financial magnitude is not disclosed, assess the
  available evidence of strategic or financial relevance.

- Unknown financial impact is not automatically
  a reason to reject an event.

- Unknown financial impact is also not automatically
  a reason to investigate an event.

- Do not set investigate=true solely because an event
  belongs to an important category.

- Set investigate=false for routine, repetitive,
  speculative, or financially insignificant news.

- Set investigate=false if the event is too uncertain
  to support a meaningful investigation.

- Keep investigate consistent with materiality
  and confidence.

- If materiality < 4 or confidence < 0.65,
  set investigate=false.


EARNINGS AND FINANCIAL RESULTS:

- Do not assign high materiality solely because
  an article mentions earnings, an earnings call,
  an earnings transcript, or an earnings presentation.

- Publishing an earnings transcript or presentation
  is not by itself a new financial event.

- If an article only announces an earnings call,
  publishes a transcript, or republishes an earnings
  presentation without substantive financial details,
  do not extract an earnings event.

- If substantive financial results are provided,
  evaluate the actual financial information.

- Consider reported changes in revenue, earnings,
  margins, profitability, cash flow, and other
  financially meaningful results when available.

- Do not assume earnings are surprising unless
  the article provides evidence of expectations,
  comparisons, or unexpected developments.

- Do not classify future earnings dates as
  reported earnings.

- Distinguish the date financial results were
  announced from the publication date of the article.


EVENT CLASSIFICATION:


earnings:
Actual reported financial results.

guidance:
Company-issued forward-looking financial guidance.

major_contract:
A company wins or signs a significant contract.

merger_acquisition:
A company announces, agrees to, or completes
an acquisition or merger.

partnership:
A company announces a business partnership.

product_launch:
A company announces or releases a new product.

regulatory:
Regulatory approvals, restrictions, investigations,
or enforcement actions.

lawsuit:
A significant legal dispute or court ruling.

management_change:
A change in CEO or other senior leadership.

financing:
Issuing debt, equity, or securing financing.

insider_activity:
Reported insider buying or selling.

analyst_rating:
An analyst upgrades, downgrades, initiates coverage,
or changes a price target.

dividend:
A company declares, increases, decreases,
suspends, or resumes a dividend.

share_buyback:
A company announces or changes a share repurchase program.

market_move:
A notable share price or trading volume movement
with concrete company-related context.

other:
A concrete company development not covered by
the categories above.


CLASSIFICATION RULES:

- Always use the most specific applicable event_type.

- Do not classify an acquisition as "other".

- Do not classify future earnings dates as earnings.

- Do not create an event solely because
  a share price moved.

- Do not create an event solely because
  trading volume changed.

- Do not create an event solely because
  earnings are approaching.

- Do not treat a repeated report of an older
  announcement as a newly occurring company event.

- Use "other" only when no specific category applies.


FINAL REQUIREMENTS:

- Extract only concrete, source-supported events.

- Do not invent information to fill missing details.

- Do not exaggerate the financial significance
  of an event.

- Do not automatically reject a potentially important
  event simply because its financial impact is unknown.

- Prefer accurate screening over generating
  a large number of candidates.

- Return all relevant extracted events.

- It is acceptable to return no events if none
  of the supplied articles contain a qualifying
  concrete company development.

- Do not make buy, sell, or hold recommendations.
"""


def fetch_news(state: NewsDiscoveryState):

    articles = get_news.invoke({})

    return {
        "raw_articles": articles
    }

def filter_articles(state: NewsDiscoveryState):

    sp500 = load_sp500()

    filtered = []
    seen = set()

    for article in state.get("raw_articles", []):

        source_uuid = article.get("uuid")

        if not source_uuid:
            continue

        for entity in article.get("entities", []):

            if entity.get("type") != "equity":
                continue

            ticker = normalize_ticker(
                entity.get("symbol") or ""
            )

            # Only S&P 500 companies
            if ticker not in sp500:
                continue

            key = (source_uuid, ticker)

            if key in seen:
                continue

            seen.add(key)

            filtered.append({
                "source_uuid": source_uuid,
                "ticker": ticker,
                "title": article.get("title", ""),
                "description": (
                    article.get("description")
                    or article.get("snippet")
                    or ""
                ),
                "published_at": article.get("published_at"),
                "url": article.get("url", ""),
                "marketaux_sentiment": entity.get(
                    "sentiment_score"
                ),
                "match_score": entity.get("match_score"),
            })

    print(
        f"S&P 500 article-ticker pairs: {len(filtered)}"
    )

    return {
        "articles": filtered
    }


def analyze_article(state: NewsDiscoveryState):

    articles = state.get("articles", [])

    if not articles:
        return {"events": []}

    all_events = []
    BATCH_SIZE = 12

    for i in range(0, len(articles), BATCH_SIZE):

        batch = articles[i:i + BATCH_SIZE]

        result = structured_llm.invoke([
            ("system", SYSTEM_PROMPT),
            ("user", json.dumps(batch))
        ])

        all_events.extend(
            event.model_dump()
            for event in result.events
        )

    return {"events": all_events}


def select_candidates(state: NewsDiscoveryState):

    articles = {
        (
            a["source_uuid"],
            normalize_ticker(a["ticker"])
        ): a
        for a in state.get("articles", [])
    }

    best_by_ticker = {}
    events_by_ticker = {}


    for event in state.get("events", []):

        ticker = normalize_ticker(event["ticker"])
        source_uuid = event["source_uuid"]

        article = articles.get((source_uuid, ticker))

        if article is None:
            continue

        qualifies = (
            event["investigate"]
            and event["materiality"] >= 4
            and event["confidence"] >= 0.65
        )


        enriched_event = {
            **event,
            "ticker": ticker,
            "headline": article["title"],
            "source_url": article["url"],
            "published_at": article["published_at"],
            "qualifies_for_investigation": qualifies,
        }

        events_by_ticker.setdefault(
            ticker, []
        ).append(enriched_event)

        if not qualifies:
            continue

        priority = round(
            event["materiality"] * 0.75
            + event["confidence"] * 10 * 0.25,
            2
        )

        previous = best_by_ticker.get(ticker)

        if (
            previous is None
            or priority > previous["priority_score"]
        ):
            best_by_ticker[ticker] = {
                **enriched_event,
                "priority_score": priority,
            }

    candidates = sorted(
        best_by_ticker.values(),
        key=lambda x: x["priority_score"],
        reverse=True
    )

    for candidate in candidates:

        ticker = candidate["ticker"]

        candidate["events"] = events_by_ticker[ticker]

        candidate["event_count"] = len(
            events_by_ticker[ticker]
        )

    print(f"Qualified candidates: {len(candidates)}")

    return {
        "candidates": candidates
    }



def group_events(state: NewsDiscoveryState):

    candidates = state.get("candidates", [])

    grouped_candidates = [
        group_candidate_events(candidate)
        for candidate in candidates
    ]

    total_groups = sum(
        candidate["unique_event_count"]
        for candidate in grouped_candidates
    )

    print(
        f"Grouped {len(grouped_candidates)} candidates "
        f"into {total_groups} unique events"
    )

    return {
        "grouped_candidates": grouped_candidates
    }