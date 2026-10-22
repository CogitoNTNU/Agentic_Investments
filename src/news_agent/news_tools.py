from langchain_core.tools import tool
import os
import requests
from datetime import datetime, timedelta, timezone
import json
import time
import feedparser
from typing import List
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
