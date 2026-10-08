from langchain_core.tools import tool
import os
import requests
from datetime import datetime, timedelta, timezone
import json
import time
import feedparser
URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"

@tool
def get_news():
    """
    Find recent market-wide news about publicly traded companies. 
    Used for discovering potentially important company events.
    """

    api_key = os.getenv("MARKETAUX_API_KEY")

    if not api_key:
        return {"error": "MARKETAUX_API_KEY is not found"}

    since = (
        datetime.now(timezone.utc) 
        - timedelta(hours=6)
    ).strftime("%Y-%m-%dT%H:%M:%S")

    response = requests.get(
        "https://api.marketaux.com/v1/news/all",
        params={
            "api_token" : api_key,
            "entity_types": "equity",
            # "countries": "",
            "language": "en",
            "must_have_entities": "true",
            "published_after": since,
            
        }
    )

    response.raise_for_status()
    data = response.json()
    
    return data.get("data",[])

URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"

@tool
def get_news_from_tickerer(ticker: List[str], limit: int = 10, days: int = 7) -> str:
    """Get last news from a list of stocks

    Args:
        ticker: Yahoo-ticker, for example 'EQNR.OL', 'MOWI.OL' (Oslo Stock Exchange) or AAPL (US)
        limit: Maximum number of newsartickles per stock (default 10)
        days: Only include artickles for the last N days (default 7)
    """
    ticker = ticker.strip().upper()
    try:
       feed = feedparser.parse(URL.format(ticker=ticker), agent="stock-news-tool")
    except Exception as e:
        return json.dump({"ticker": ticker, "error": str(e)})
    
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

