import os
from dataclasses import dataclass
from typing import List, Optional


def _split_csv_env(value: str) -> List[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class AppConfig:
    # External API credentials
    fmp_api_key: Optional[str]
    newsapi_keys: List[str]
    benzinga_token: Optional[str]
    reddit_client_id: Optional[str]
    reddit_client_secret: Optional[str]
    reddit_user_agent: Optional[str]

    # NLP
    sentiment_model: str


def load_config() -> AppConfig:
    """
    Load configuration from environment variables.
    English-only comment requirement: This module intentionally contains only English comments/docstrings.
    """
    newsapi_raw = os.getenv("NEWSAPI_KEYS", "")
    return AppConfig(
        fmp_api_key=os.getenv("FMP_API_KEY"),
        newsapi_keys=_split_csv_env(newsapi_raw),
        benzinga_token=os.getenv("BENZINGA_TOKEN"),
        reddit_client_id=os.getenv("REDDIT_CLIENT_ID"),
        reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        reddit_user_agent=os.getenv("REDDIT_USER_AGENT"),
        sentiment_model=os.getenv(
            "SENTIMENT_MODEL",
            "distilbert/distilbert-base-uncased-finetuned-sst-2-english",
        ),
    )


def require(value: Optional[str], name: str) -> str:
    if value and value.strip():
        return value.strip()
    raise RuntimeError(f"Missing required configuration: {name}")

