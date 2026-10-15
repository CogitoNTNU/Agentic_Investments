from typing import TypedDict

class NewsDiscoveryState(TypedDict):
    raw_articles: list[dict]
    articles: list[dict]
    events: list[dict]
    candidates: list[dict]
    
