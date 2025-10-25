"""OpenRouter API client for Models API, Providers API, and usage accounting"""

from typing import Any, Dict, List, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog

logger = structlog.get_logger(__name__)

BASE_URL = "https://openrouter.ai"


class OpenRouterClient:
    """Client for interacting with OpenRouter APIs"""

    def __init__(
        self,
        api_key: str,
        timeout: int = 30,
        http_referer: str = "https://pricing-tracker.example",
    ):
        """
        Initialize OpenRouter client

        Args:
            api_key: OpenRouter API key
            timeout: Request timeout in seconds
            http_referer: HTTP referer for attribution
        """
        self.api_key = api_key
        self.timeout = timeout
        self.http_referer = http_referer

        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": http_referer,
                "X-Title": "PricingTracker",
            },
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def list_models(self) -> List[Dict[str, Any]]:
        """
        Fetch all models from OpenRouter Models API

        Returns:
            List of model dictionaries with pricing and metadata

        Raises:
            httpx.HTTPError: On API errors
        """
        logger.info("fetching_models_from_openrouter")

        try:
            response = self._client.get(f"{BASE_URL}/api/v1/models")
            response.raise_for_status()
            data = response.json()

            models = data.get("data", [])
            logger.info("models_fetched", count=len(models))

            return models

        except httpx.HTTPError as e:
            logger.error("failed_to_fetch_models", error=str(e))
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def list_providers(self) -> List[Dict[str, Any]]:
        """
        Fetch all providers from OpenRouter Providers API

        Returns:
            List of provider dictionaries

        Raises:
            httpx.HTTPError: On API errors
        """
        logger.info("fetching_providers_from_openrouter")

        try:
            response = self._client.get(f"{BASE_URL}/api/v1/providers")
            response.raise_for_status()
            data = response.json()

            providers = data.get("data", [])
            logger.info("providers_fetched", count=len(providers))

            return providers

        except httpx.HTTPError as e:
            logger.error("failed_to_fetch_providers", error=str(e))
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def get_model_page_html(self, model_path: str) -> str:
        """
        Fetch HTML for a model's public page (for scraping provider list)

        Args:
            model_path: Model path like 'deepseek/deepseek-r1'

        Returns:
            HTML content as string

        Raises:
            httpx.HTTPError: On request errors
        """
        url = f"{BASE_URL}/{model_path}"
        logger.info("fetching_model_page", url=url)

        try:
            response = self._client.get(url)
            response.raise_for_status()
            return response.text

        except httpx.HTTPError as e:
            logger.error("failed_to_fetch_model_page", url=url, error=str(e))
            raise

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def tiny_byok_call(self, model_slug: str) -> Dict[str, Any]:
        """
        Make a minimal BYOK request to verify pricing via usage accounting

        Args:
            model_slug: OpenRouter model slug (e.g., 'anthropic/claude-3.5-sonnet')

        Returns:
            Response JSON with usage details including cost and upstream_inference_cost

        Raises:
            httpx.HTTPError: On API errors
        """
        logger.info("making_byok_verification_call", model=model_slug)

        payload = {
            "model": model_slug,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "usage": {"include": True},  # Enable usage accounting
        }

        try:
            response = self._client.post(
                f"{BASE_URL}/api/v1/chat/completions", json=payload
            )
            response.raise_for_status()
            result = response.json()

            logger.info(
                "byok_call_completed", model=model_slug, usage=result.get("usage")
            )

            return result

        except httpx.HTTPError as e:
            logger.error("byok_call_failed", model=model_slug, error=str(e))
            raise

    def close(self):
        """Close the HTTP client"""
        self._client.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
