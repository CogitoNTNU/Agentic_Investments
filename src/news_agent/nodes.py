
import json
from state import NewsDiscoveryState
from news_tools import get_news
from schemas import NewsAnalysis
from src.model import get_model


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
            You are a financial news analysis agent.

            Analyze the provided news articles and identify
            meaningful company events.

            Do not make investment recommendations.

            Determine:
            - ticker
            - event type
            - summary
            - sentiment
            - materiality
            - novelty
            - confidence
            - whether the event deserves further investigation
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
