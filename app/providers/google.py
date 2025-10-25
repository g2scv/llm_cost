"""Google (Gemini) provider adapter"""

from typing import Optional, Callable
from decimal import Decimal
import structlog

from .base import ProviderAdapter, PricingResult

logger = structlog.get_logger(__name__)


class GoogleAdapter(ProviderAdapter):
    """Adapter for Google AI pricing"""

    slug = "google"

    def __init__(self, brave_search_fn: Optional[Callable] = None):
        self.brave_search_fn = brave_search_fn

    async def resolve(
        self, model_name: str, model_slug: str
    ) -> Optional[PricingResult]:
        """
        Resolve Google AI pricing

        Known pricing URLs:
        - https://ai.google.dev/pricing
        - https://cloud.google.com/vertex-ai/generative-ai/pricing
        """
        logger.info("resolving_google_pricing", model=model_slug)

        # Google's official pricing page
        pricing_url = "https://ai.google.dev/pricing"

        # For now, return the URL for manual verification
        # In production, you would scrape this page
        logger.debug(
            "google_pricing_requires_manual_check",
            model=model_slug,
            url=pricing_url,
        )

        return None  # Delegate to generic adapter for now
