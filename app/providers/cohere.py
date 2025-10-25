"""Cohere provider adapter"""

from typing import Optional, Callable
import structlog

from .base import ProviderAdapter, PricingResult

logger = structlog.get_logger(__name__)


class CohereAdapter(ProviderAdapter):
    """Adapter for Cohere pricing"""

    slug = "cohere"

    def __init__(self, brave_search_fn: Optional[Callable] = None):
        self.brave_search_fn = brave_search_fn

    async def resolve(
        self, model_name: str, model_slug: str
    ) -> Optional[PricingResult]:
        """Resolve Cohere pricing"""
        logger.info("resolving_cohere_pricing", model=model_slug)

        # Cohere pricing page
        pricing_url = "https://cohere.com/pricing"

        logger.debug("cohere_pricing_check", model=model_slug, url=pricing_url)

        return None  # Delegate to generic adapter
