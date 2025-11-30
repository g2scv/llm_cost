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

    # Model Filtering (OpenRouter query params)
    # Comma-separated list of required supported_parameters
    model_filter_supported_parameters: str = "structured_outputs,response_format,stop"
    # Set to true to exclude distillable models
    model_filter_distillable: bool = False
    # Input modalities filter (text, image, audio, video)
    model_filter_input_modalities: str = "text"
    # Output modalities filter (text, image, embeddings)
    model_filter_output_modalities: str = "text"

    # Docker Scheduler Settings (for containerized deployment)
    run_interval_hours: int = 24
    run_on_startup: bool = True
    auto_sync_backend: bool = True
    check_missing_models: bool = True

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )


def load_config() -> Config:
    """Load and validate configuration"""
    return Config()
