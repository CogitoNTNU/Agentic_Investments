
import json
from .state import NewsDiscoveryState
from .news_tools import get_news
from .schemas import NewsAnalysis
from ..model import get_model


llm = get_model()

structured_llm = llm.with_structured_output(NewsAnalysis)


def fetch_news(state: NewsDiscoveryState):

    articles = get_news.invoke({})

    return {
        "raw_articles": articles
    }


def analyze_article(state: NewsDiscoveryState):

    articles = state["raw_articles"]

    if not articles:
        return {
            "events": []
        }

    result = structured_llm.invoke([
        (
        "system",
            """
            You are a financial news event extraction system.

            Analyze ONLY the articles provided by the user.

            Rules:
            - Every event must be directly supported by one of the provided articles.
            - Do not use outside knowledge.
            - Do not infer or invent events that are not explicitly described.
            - Never combine facts from unrelated articles.
            - Set source_uuid to the UUID of the article supporting the event.
            - If an article contains no meaningful company event, do not create an event for it.
            - Summaries must only contain information found in the source article.
            - An analyst upgrade/downgrade should use event_type="analyst_rating".
            - materiality and novelty use a 0-10 scale.
            - confidence uses a 0-1 scale.
            - sentiment uses a -1 to 1 scale.

            Extract:
            - source_uuid
            - ticker
            - event type
            - summary
            - sentiment
            - materiality
            - novelty
            - confidence
            - investigate

            Scales:

            sentiment:
            -1 = very negative
            0 = neutral
            1 = very positive

            materiality:
            0 = completely immaterial
            10 = extremely material

            novelty:
            0 = completely expected or already known
            10 = highly novel or unexpected

            confidence:
            0 = very uncertain
            1 = very confident

            Event classification rules:

            - analyst_rating:
            An analyst or brokerage explicitly upgrades, downgrades,
            initiates coverage, or changes a price target.

            - dividend:
            The company declares, increases, decreases, suspends,
            or resumes a dividend.

            - market_move:
            The main event is a stock-price move, unusual volume,
            options activity, or general market reaction without
            another clear corporate event.

            - earnings:
            Actual reported financial results.

            - guidance:
            Company-issued forward-looking revenue, earnings,
            margin, EBITDA, or similar guidance.

            Do not use analyst_rating as a fallback category.
            Use "other" if no category clearly applies.
            
            Only create an event if the article describes a concrete
            company-specific development.

            Do NOT create an event solely because:
            - the share price moved
            - trading volume changed
            - options activity increased
            - the broader market moved
            - investors are anticipating earnings

            If there is no concrete company event, omit the article.
            """
        ),
        (
            "user",
            json.dumps(articles)
        )
    ])

    return {
        "events": [
            event.model_dump()
            for event in result.events
        ]
    }
