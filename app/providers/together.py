"""Together AI provider adapter"""

from typing import Optional, Callable
import structlog

from .base import ProviderAdapter, PricingResult

logger = structlog.get_logger(__name__)


class TogetherAdapter(ProviderAdapter):
    """Adapter for Together AI pricing"""

    slug = "together"

    def __init__(self, brave_search_fn: Optional[Callable] = None):
        self.brave_search_fn = brave_search_fn

    async def resolve(
        self, model_name: str, model_slug: str
    ) -> Optional[PricingResult]:
        """Resolve Together AI pricing"""
        logger.info("resolving_together_pricing", model=model_slug)

        pricing_url = "https://www.together.ai/pricing"

        logger.debug("together_pricing_check", model=model_slug, url=pricing_url)

        return None  # Delegate to generic adapter
