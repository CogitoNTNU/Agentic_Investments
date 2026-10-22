from langchain_core.tools import tool
import os
import requests
from datetime import datetime, timedelta, timezone
import json
import time
import feedparser
from typing import List
from .sp500 import load_sp500
import random
URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"



sp500 = load_sp500()

symbols = ",".join(sorted(sp500))

@tool
def get_news() -> list[dict]:
    """
    Fetch recent financial news for S&P 500 companies
    using the Marketaux API.

    Returns a list of news articles containing company
    information, stock tickers, and sentiment scores.
    """

    api_key = os.getenv("MARKETAUX_API_KEY")

    if not api_key:
        raise RuntimeError("MARKETAUX_API_KEY missing")

    since = (
        datetime.now(timezone.utc)
        - timedelta(hours=26)
    ).strftime("%Y-%m-%dT%H:%M:%S")

    # Load S&P 500 tickers
    tickers = sorted(load_sp500())

    TEST_MODE = True

    GROUP_SIZE = 25
    PAGES_PER_GROUP = 1 if TEST_MODE else 2
    LIMIT = 3

    all_articles = {}

    # Split the index into groups
    groups = [
        tickers[i:i + GROUP_SIZE]
        for i in range(0, len(tickers), GROUP_SIZE)
    ]
    
    selected_groups = (
    random.Random(44).sample(groups, 3)
    if TEST_MODE
    else groups
    )

    for group_number, group in enumerate(selected_groups, start=1):

        symbols = ",".join(group)

        for page in range(1, PAGES_PER_GROUP + 1):

            response = requests.get(
                "https://api.marketaux.com/v1/news/all",
                params={
                    "api_token": api_key,
                    "symbols": symbols,
                    "entity_types": "equity",
                    "language": "en",
                    "filter_entities": "true",
                    "group_similar": "false",
                    "published_after": since,
                    "limit": LIMIT,
                    "page": page,
                },
                timeout=20,
            )

            response.raise_for_status()

            articles = response.json().get("data", [])

            for article in articles:
                uuid = article.get("uuid")

                if uuid:
                    all_articles[uuid] = article

            print(
                f"Group {group_number}/{len(groups)}, "
                f"page {page}: {len(articles)} articles"
            )

            if len(articles) < LIMIT:
                break

    print(f"Unique articles: {len(all_articles)}")

    return list(all_articles.values())

URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"

@tool
def get_news_from_tickerer(ticker: str, limit: int = 10, days: int = 7) -> str:
    """Get the latest news for a single stock.

    Args:
        ticker: Yahoo-ticker, for example 'EQNR.OL', 'MOWI.OL' (Oslo Stock Exchange) or AAPL (US)
        limit: Maximum number of newsartickles per stock (default 10)
        days: Only include artickles for the last N days (default 7)
    """
    ticker = ticker.strip().upper()
    try:
       feed = feedparser.parse(URL.format(ticker=ticker), agent="stock-news-tool")
    except Exception as e:
        return json.dumps({"ticker": ticker, "error": str(e)})
    
    cutoff = time.time() - days*86400
    articles = []
    for entry in feed.entries:
        if entry.get("published_parsed") and time.mktime(entry.published_parsed)>=cutoff:
            articles.append({
                "title": entry.get("title", "").strip(),
                "summary": entry.get("summary", "")[:1000],
                "published": entry.get("published", ""),
                "link": entry.get("link", ""),

        })  
        if len(articles)>=limit:
            break  
    if not articles:
        return json.dumps({
            "ticker": ticker,
            "articles": [],
            "note": "No articles found. Check the ticker (Oslo Børs tickers end in .OL) or increase 'days'.",
            })
    return json.dumps({"ticker": ticker, "articles": articles})

# print(get_news_from_tickerer.invoke({"ticker": "AAPL"}))
