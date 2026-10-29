from langchain_core.tools import tool

import os
import json
import time
import hashlib
import requests

from pathlib import Path
from datetime import datetime, timedelta, timezone

from .sp500 import load_sp500




MARKETAUX_URL = "https://api.marketaux.com/v1/news/all"

TEST_MODE = False

GROUP_SIZE = 25
PAGES_PER_GROUP = 1 if TEST_MODE else 4
LIMIT = 3

LOOKBACK_HOURS = 26

REQUEST_DELAY_SECONDS = 4
MAX_RETRIES = 4

OUTPUT_DIR = Path("data/news_discovery")

CHECKPOINT_PATH = (
    OUTPUT_DIR / "marketaux_checkpoint.json"
)

RAW_ARTICLES_PATH = (
    OUTPUT_DIR / "marketaux_raw_articles.json"
)


# ==========================================
# JSON HELPERS
# ==========================================

def _save_json(path: Path, data) -> None:
    """
    Save JSON atomically.

    Writing to a temporary file first reduces
    the risk of a corrupted checkpoint.
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporary_path = path.with_suffix(
        path.suffix + ".tmp"
    )

    temporary_path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    temporary_path.replace(path)


def _load_json(path: Path):
    """
    Read a JSON file.
    """

    return json.loads(
        path.read_text(encoding="utf-8")
    )


# ==========================================
# MARKET AUX REQUEST
# ==========================================

def _fetch_page(
    api_key: str,
    symbols: str,
    since: str,
    page: int,
) -> list[dict]:
    """
    Fetch one Marketaux page.

    Handles:
    - Request pacing
    - HTTP 429 rate limits
    - HTTP 402 quota exhaustion
    - Temporary network failures
    - Temporary server errors

    API tokens are not included in our
    custom error messages.
    """

    params = {
        "api_token": api_key,
        "symbols": symbols,
        "entity_types": "equity",
        "language": "en",
        "filter_entities": "true",
        "group_similar": "false",
        "published_after": since,
        "limit": LIMIT,
        "page": page,
    }

    for attempt in range(MAX_RETRIES):

        # Slow down consecutive API requests
        time.sleep(REQUEST_DELAY_SECONDS)

        try:
            response = requests.get(
                MARKETAUX_URL,
                params=params,
                timeout=30,
            )

        except requests.RequestException:

            if attempt == MAX_RETRIES - 1:
                raise RuntimeError(
                    "Marketaux request failed after "
                    "multiple network retries."
                ) from None

            wait_seconds = 10 * (attempt + 1)

            print(
                f"Network error. Retrying in "
                f"{wait_seconds} seconds..."
            )

            time.sleep(wait_seconds)
            continue

        # ----------------------------------
        # Rate limit reached
        # ----------------------------------

        if response.status_code == 429:

            if attempt == MAX_RETRIES - 1:
                raise RuntimeError(
                    "Marketaux rate limit persisted "
                    "after all retry attempts."
                )

            retry_after = response.headers.get(
                "Retry-After", ""
            )

            wait_seconds = (
                int(retry_after)
                if retry_after.isdigit()
                else 65
            )

            wait_seconds = max(1, wait_seconds)

            print(
                f"Marketaux rate limit reached. "
                f"Waiting {wait_seconds} seconds..."
            )

            time.sleep(wait_seconds)
            continue

        # ----------------------------------
        # Subscription quota exhausted
        # ----------------------------------

        if response.status_code == 402:
            raise RuntimeError(
                "Marketaux subscription quota exhausted. "
                "Collected articles are saved in the "
                "checkpoint. Resume when quota is available."
            )

        # ----------------------------------
        # Temporary server errors
        # ----------------------------------

        if response.status_code in (500, 502, 503, 504):

            if attempt == MAX_RETRIES - 1:
                raise RuntimeError(
                    "Marketaux server error after "
                    "all retry attempts."
                )

            wait_seconds = 10 * (attempt + 1)

            print(
                f"Marketaux server error "
                f"{response.status_code}. "
                f"Retrying in {wait_seconds} seconds..."
            )

            time.sleep(wait_seconds)
            continue

        # ----------------------------------
        # Other API errors
        # ----------------------------------

        if response.status_code != 200:
            raise RuntimeError(
                f"Marketaux returned HTTP "
                f"{response.status_code}."
            )

        # ----------------------------------
        # Successful response
        # ----------------------------------

        try:
            payload = response.json()
        except ValueError:
            raise RuntimeError(
                "Marketaux returned invalid JSON."
            ) from None

        articles = payload.get("data", [])

        if not isinstance(articles, list):
            raise RuntimeError(
                "Marketaux returned an invalid "
                "article collection."
            )

        return articles

    raise RuntimeError(
        "Marketaux request failed unexpectedly."
    )


# ==========================================
# NEWS FETCHING TOOL
# ==========================================

@tool
def get_news() -> list[dict]:
    """
    Fetch recent financial news for S&P 500 companies
    using the Marketaux API.

    Supports:
    - Full S&P 500 coverage
    - Pagination
    - Rate-limit handling
    - UUID deduplication
    - Checkpointing
    - Resume after failure
    - Cached raw articles

    Returns:
        list[dict]: Unique Marketaux news articles.
    """

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # ----------------------------------
    # Optional cached-data mode
    # ----------------------------------

    use_saved_raw = (
        os.getenv("NEWS_USE_SAVED_RAW", "0") == "1"
    )

    if use_saved_raw:

        if not RAW_ARTICLES_PATH.exists():
            raise FileNotFoundError(
                f"No cached articles found at "
                f"{RAW_ARTICLES_PATH}"
            )

        articles = _load_json(RAW_ARTICLES_PATH)

        print(
            f"Loaded {len(articles)} cached "
            f"articles from {RAW_ARTICLES_PATH}"
        )

        return articles

    # ----------------------------------
    # API credentials
    # ----------------------------------

    api_key = os.getenv("MARKETAUX_API_KEY")

    if not api_key:
        raise RuntimeError(
            "MARKETAUX_API_KEY missing"
        )

    # ----------------------------------
    # Load S&P 500 companies
    # ----------------------------------

    tickers = sorted(load_sp500())

    groups = [
        tickers[i:i + GROUP_SIZE]
        for i in range(0, len(tickers), GROUP_SIZE)
    ]

    print(
        f"\nS&P 500 symbols: {len(tickers)}"
    )

    print(
        f"Ticker groups: {len(groups)}"
    )

    print(
        f"Maximum pages per group: {PAGES_PER_GROUP}"
    )

    # ----------------------------------
    # Identify collection configuration
    # ----------------------------------

    configuration = {
        "tickers": tickers,
        "group_size": GROUP_SIZE,
        "pages_per_group": PAGES_PER_GROUP,
        "limit": LIMIT,
        "lookback_hours": LOOKBACK_HOURS,
    }

    configuration_signature = hashlib.sha256(
        json.dumps(
            configuration,
            sort_keys=True
        ).encode("utf-8")
    ).hexdigest()

    # ----------------------------------
    # Default fresh-run settings
    # ----------------------------------

    since = (
        datetime.now(timezone.utc)
        - timedelta(hours=LOOKBACK_HOURS)
    ).strftime("%Y-%m-%dT%H:%M:%S")

    started_at = datetime.now(
        timezone.utc
    ).isoformat()

    all_articles = {}

    start_group = 0
    start_page = 1

    # ----------------------------------
    # Resume existing checkpoint
    # ----------------------------------

    reset_checkpoint = (
        os.getenv("NEWS_RESET", "0") == "1"
    )

    if (
        CHECKPOINT_PATH.exists()
        and not reset_checkpoint
    ):

        checkpoint = _load_json(
            CHECKPOINT_PATH
        )

        if not checkpoint.get("completed", False):

            if (
                checkpoint.get("configuration_signature")
                != configuration_signature
            ):
                raise RuntimeError(
                    "An incomplete checkpoint exists with "
                    "different settings. Set NEWS_RESET=1 "
                    "to start a new collection."
                )

            since = checkpoint["since"]

            started_at = checkpoint["started_at"]

            start_group = checkpoint["next_group"]
            start_page = checkpoint["next_page"]

            all_articles = {
                article["uuid"]: article
                for article in checkpoint["articles"]
                if article.get("uuid")
            }

            print(
                "\n=== RESUMING NEWS COLLECTION ==="
            )

            print(
                f"Previously collected: "
                f"{len(all_articles)} articles"
            )

            print(
                f"Resuming at group "
                f"{start_group + 1}, "
                f"page {start_page}"
            )

            print(
                f"Original published_after: {since}"
            )

    # ----------------------------------
    # Collect news
    # ----------------------------------

    print(
        "\n=== STARTING MARKETAUX COLLECTION ==="
    )

    print(
        f"Published after: {since}"
    )

    for group_index in range(
        start_group,
        len(groups)
    ):

        group = groups[group_index]

        symbols = ",".join(group)

        first_page = (
            start_page
            if group_index == start_group
            else 1
        )

        for page in range(
            first_page,
            PAGES_PER_GROUP + 1
        ):

            # Fetch page with retry handling
            articles = _fetch_page(
                api_key=api_key,
                symbols=symbols,
                since=since,
                page=page,
            )

            # ----------------------------------
            # Add unique articles
            # ----------------------------------

            for article in articles:

                uuid = article.get("uuid")

                if uuid:
                    all_articles[uuid] = article

            print(
                f"Group {group_index + 1}/{len(groups)}, "
                f"page {page}: "
                f"{len(articles)} articles "
                f"| unique total: {len(all_articles)}"
            )

            # ----------------------------------
            # Determine next checkpoint cursor
            # ----------------------------------

            group_finished = (
                len(articles) < LIMIT
                or page == PAGES_PER_GROUP
            )

            if group_finished:

                next_group = group_index + 1
                next_page = 1

            else:

                next_group = group_index
                next_page = page + 1

            # ----------------------------------
            # Save checkpoint after every page
            # ----------------------------------

            checkpoint_data = {
                "completed": False,
                "started_at": started_at,
                "since": since,
                "configuration_signature": (
                    configuration_signature
                ),
                "next_group": next_group,
                "next_page": next_page,
                "articles": list(
                    all_articles.values()
                ),
            }

            _save_json(
                CHECKPOINT_PATH,
                checkpoint_data
            )

            # Stop paging this group if
            # fewer articles than LIMIT returned
            if group_finished:
                break

    # ----------------------------------
    # Save completed raw batch
    # ----------------------------------

    unique_articles = list(
        all_articles.values()
    )

    _save_json(
        RAW_ARTICLES_PATH,
        unique_articles
    )

    # ----------------------------------
    # Mark checkpoint completed
    # ----------------------------------

    completed_checkpoint = {
        "completed": True,
        "started_at": started_at,
        "finished_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "since": since,
        "configuration_signature": (
            configuration_signature
        ),
        "next_group": len(groups),
        "next_page": 1,
        "articles": unique_articles,
    }

    _save_json(
        CHECKPOINT_PATH,
        completed_checkpoint
    )

    print(
        "\n=== NEWS COLLECTION COMPLETE ==="
    )

    print(
        f"Unique articles: "
        f"{len(unique_articles)}"
    )

    print(
        f"Saved raw articles: "
        f"{RAW_ARTICLES_PATH}"
    )

    return unique_articles