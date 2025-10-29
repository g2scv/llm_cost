"""Configuration management using pydantic-settings"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Config(BaseSettings):
    """Application configuration loaded from environment variables"""

    # Supabase
    supabase_url: str
    supabase_service_key: str

    # Secondary Supabase (g2scv backend)
    backend_supabase_url: Optional[str] = None
    backend_supabase_service_key: Optional[str] = None

    # OpenRouter
    openrouter_api_key: str

    # Backend defaults
    default_chat_model_id: Optional[str] = None
    default_embedding_model_id: Optional[str] = None

    # Brave Search API (for provider pricing scraping)
    brave_api_key: Optional[str] = None

    # HTTP settings
    http_proxy: Optional[str] = None
    request_timeout_seconds: int = 30
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    )

    # Playwright
    headless: bool = True

    # Logging
    log_level: str = "INFO"

    # Validation
    price_change_threshold_percent: float = 30.0

    # Provider scraping (disable to avoid Brave API rate limits)
    enable_provider_scraping: bool = False

    # Concurrency
    max_parallel_models: int = 10

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )


def load_config() -> Config:
    """Load and validate configuration"""
    return Config()
