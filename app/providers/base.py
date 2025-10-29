"""Base interface for provider pricing adapters"""

from abc import ABC, abstractmethod
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, ConfigDict
import structlog

logger = structlog.get_logger(__name__)


class PricingResult(BaseModel):
    """Pricing information resolved from a provider"""

    prompt_usd_per_million: Optional[Decimal] = None
    completion_usd_per_million: Optional[Decimal] = None
    request_usd: Optional[Decimal] = None
    image_usd: Optional[Decimal] = None
    web_search_usd: Optional[Decimal] = None
    internal_reasoning_usd_per_million: Optional[Decimal] = None
    input_cache_read_usd_per_million: Optional[Decimal] = None
    input_cache_write_usd_per_million: Optional[Decimal] = None

    source_url: str
    notes: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ProviderAdapter(ABC):
    """
    Abstract base class for provider-specific pricing resolvers

    Each provider adapter knows:
    1. Where to find pricing info (URLs, selectors)
    2. How to parse that info
    3. How to normalize it to per-1M USD
    """

    slug: str  # Provider slug (e.g., 'openai')

    @abstractmethod
    async def resolve(
        self, model_name: str, model_slug: str
    ) -> Optional[PricingResult]:
        """
        Resolve pricing for a specific model

        Args:
            model_name: Human-readable model name
            model_slug: OpenRouter model slug

        Returns:
            PricingResult if found, None otherwise
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} slug={self.slug}>"
