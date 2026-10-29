"""
Yahoo Finance news tool for single stocks.

Used by the news sub-agent (src/news_agent/news_agent.py).
Install:  pip install langchain-core feedparser requests
"""
import calendar
import html
import json
import re
import time
from datetime import datetime, timezone

import feedparser
import requests
from langchain_core.tools import tool
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

YAHOO_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; stock-news-tool/1.0)"}
TICKER_PATTERN = re.compile(r"^[A-Z0-9.\-^=]{1,15}$")

MAX_LIMIT = 20
MAX_DAYS = 30
TITLE_CHARS = 300
SUMMARY_CHARS = 1000
CACHE_TTL = 600  # seconds; avoids refetching when the agent asks twice
_cache: dict = {}

# Retries on timeouts, connection errors and 429/5xx, with a short backoff
_session = requests.Session()
_session.mount(
    "https://",
    HTTPAdapter(max_retries=Retry(total=2, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504))),
)


def _clean(text: str, max_len: int) -> str:
    """Strip HTML tags and extra whitespace, then cut to max_len."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def _fetch_feed(ticker: str):
    cached = _cache.get(ticker)
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]

    response = _session.get(
        YAHOO_URL,
        params={"s": ticker, "region": "US", "lang": "en-US"},  # safely URL-encoded
        headers=HEADERS,
        timeout=10,
    )
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    _cache[ticker] = (time.time(), feed)  # only successful fetches are cached
    return feed


@tool
def get_news_from_tickerer(ticker: str, limit: int = 10, days: int = 7) -> str:
    """Get the latest news for a single stock, newest first.

    Args:
        ticker: Yahoo ticker, e.g. 'EQNR.OL', 'MOWI.OL' (Oslo Børs) or 'AAPL' (US).
        limit: Maximum number of articles (default 10, max 20).
        days: Only include articles from the last N days (default 7, max 30).
    """
    ticker = (ticker or "").strip().upper()
    if not TICKER_PATTERN.match(ticker):
        return json.dumps({"error": f"Invalid ticker: {ticker!r}"})

    limit = max(1, min(limit, MAX_LIMIT))
    days = max(1, min(days, MAX_DAYS))

    try:
        feed = _fetch_feed(ticker)
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else None
        if code == 404:
            return json.dumps({
                "ticker": ticker,
                "error": "No news feed found for this ticker. Check the ticker "
                         "(Oslo Børs tickers end in .OL).",
            })
        return json.dumps({"ticker": ticker, "error": f"Yahoo returned HTTP {code}"})
    except requests.RequestException as e:
        return json.dumps({"ticker": ticker, "error": f"Could not fetch news: {e}"})

    # feedparser reports broken feeds via 'bozo' instead of raising
    if feed.bozo and not feed.entries:
        return json.dumps({"ticker": ticker, "error": str(feed.get("bozo_exception"))})

    cutoff = time.time() - days * 86400
    articles, seen = [], set()
    for entry in feed.entries:
        parsed = entry.get("published_parsed")
        if not parsed:
            continue
        ts = calendar.timegm(parsed)  # feedparser dates are UTC
        if ts < cutoff:
            continue

        link = entry.get("link", "")
        title = _clean(entry.get("title", ""), TITLE_CHARS)
        key = link or title
        if key in seen:  # skip duplicates
            continue
        seen.add(key)

        articles.append({
            "_ts": ts,
            "title": title,
            "summary": _clean(entry.get("summary", ""), SUMMARY_CHARS),
            "published": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "link": link,
        })

    articles.sort(key=lambda a: a["_ts"], reverse=True)  # newest first
    articles = [{k: v for k, v in a.items() if k != "_ts"} for a in articles[:limit]]

    result = {"ticker": ticker, "days_searched": days, "count": len(articles), "articles": articles}
    if not articles:
        result["note"] = (
            "No articles found. Check the ticker (Oslo Børs tickers end in .OL) "
            "or increase 'days'."
        )
    return json.dumps(result, ensure_ascii=False)


# Only runs when you execute this file directly, not when it is imported
if __name__ == "__main__":
    print(get_news_from_tickerer.invoke({"ticker": "CHTR"}))