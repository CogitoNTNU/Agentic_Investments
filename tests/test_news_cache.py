from unittest.mock import MagicMock


def test_yahoo_feeds_are_not_retained_between_requests(monkeypatch):
    from src.news_agent import news_tools

    response = MagicMock(content=b"feed")
    fetch = MagicMock(return_value=response)
    monkeypatch.setattr(news_tools._session, "get", fetch)
    monkeypatch.setattr(news_tools.feedparser, "parse", lambda content: {"entries": []})
    news_tools._fetch_feed("AAPL")
    news_tools._fetch_feed("MSFT")
    news_tools._fetch_feed("AAPL")
    assert fetch.call_count == 3
