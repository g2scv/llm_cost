"""OpenAI provider adapter using Brave Search MCP"""

from typing import Optional
from decimal import Decimal
import re
import structlog

from .base import ProviderAdapter, PricingResult

logger = structlog.get_logger(__name__)


class OpenAIAdapter(ProviderAdapter):
    """
    Adapter for OpenAI pricing using Brave Search MCP

    This adapter searches for OpenAI pricing information using Brave Search
    and extracts pricing data from credible sources.
    """

    slug = "openai"

    # Known pricing patterns for OpenAI models (fallback if search fails)
    KNOWN_MODELS = {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-4": {"input": 30.00, "output": 60.00},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        "o1": {"input": 15.00, "output": 60.00},
        "o1-mini": {"input": 3.00, "output": 12.00},
        "o1-pro": {"input": 150.00, "output": 600.00},
    }

    def __init__(self, brave_search_fn=None):
        """
        Initialize OpenAI adapter

        Args:
            brave_search_fn: Function to call Brave Search MCP (injected for testing)
        """
        self.brave_search = brave_search_fn

    async def resolve(
        self, model_name: str, model_slug: str
    ) -> Optional[PricingResult]:
        """
        Resolve OpenAI model pricing using Brave Search

        Args:
            model_name: Human-readable model name (e.g., "GPT-4o")
            model_slug: OpenRouter model slug (e.g., "openai/gpt-4o")

        Returns:
            PricingResult if pricing found, None otherwise
        """
        logger.info("resolving_openai_pricing", model=model_name, slug=model_slug)

        # Extract OpenAI model name from slug
        if "/" in model_slug:
            _, openai_model = model_slug.split("/", 1)
        else:
            openai_model = model_name.lower()

        # Try Brave Search first
        if self.brave_search:
            result = await self._search_pricing(openai_model)
            if result:
                return result

        # Fallback to known pricing
        result = self._get_known_pricing(openai_model)
        if result:
            logger.info("using_known_openai_pricing", model=openai_model)
            return result

        logger.warning("openai_pricing_not_found", model=openai_model)
        return None

    async def _search_pricing(self, model_name: str) -> Optional[PricingResult]:
        """
        Search for OpenAI pricing using Brave Search

        Args:
            model_name: OpenAI model name

        Returns:
            PricingResult if found in search results
        """
        if not self.brave_search:
            return None

        try:
            # Construct search query
            query = f"OpenAI {model_name} API pricing per million tokens 2025"

            logger.info("searching_brave", query=query)

            # Call Brave Search (this would be injected from the pipeline)
            results = await self.brave_search(query, count=5)

            # Extract pricing from search results
            prices = self._extract_prices_from_results(results)

            if prices:
                return PricingResult(
                    prompt_usd_per_million=Decimal(str(prices["input"])),
                    completion_usd_per_million=Decimal(str(prices["output"])),
                    request_usd=None,
                    source_url=prices.get(
                        "source_url", "https://openai.com/api/pricing/"
                    ),
                )

        except Exception as e:
            logger.error("brave_search_failed", model=model_name, error=str(e))

        return None

    def _extract_prices_from_results(self, search_results: list) -> Optional[dict]:
        """
        Extract pricing from Brave Search results

        Looks for patterns like:
        - $X per million input tokens
        - $Y per million output tokens
        """
        # Patterns to match pricing
        patterns = [
            # "$15 per million input tokens and $75 per million output tokens"
            r"\$(\d+(?:\.\d+)?)\s*per\s+million\s+input\s+tokens?\s+and\s+\$(\d+(?:\.\d+)?)\s*per\s+million\s+output",
            # "$15/million input, $75/million output"
            r"\$(\d+(?:\.\d+)?)/million\s+input[,\s]+\$(\d+(?:\.\d+)?)/million\s+output",
            # "$15 (input), $75 (output) per million tokens"
            r"\$(\d+(?:\.\d+)?)\s*\(input\)[,\s]+\$(\d+(?:\.\d+)?)\s*\(output\)",
        ]

        for result in search_results:
            description = result.get("description", "")

            for pattern in patterns:
                match = re.search(pattern, description, re.IGNORECASE)
                if match:
                    input_price = float(match.group(1))
                    output_price = float(match.group(2))

                    logger.info(
                        "extracted_pricing_from_search",
                        input=input_price,
                        output=output_price,
                        source=result.get("url"),
                    )

                    return {
                        "input": input_price,
                        "output": output_price,
                        "source_url": result.get("url", ""),
                    }

        return None

    def _get_known_pricing(self, model_name: str) -> Optional[PricingResult]:
        """
        Get pricing from known model list (fallback)

        Args:
            model_name: OpenAI model name

        Returns:
            PricingResult if model is in known list
        """
        # Normalize model name
        normalized = model_name.lower().replace("-", "-").strip()

        # Try exact match first
        if normalized in self.KNOWN_MODELS:
            prices = self.KNOWN_MODELS[normalized]
            return PricingResult(
                prompt_usd_per_million=Decimal(str(prices["input"])),
                completion_usd_per_million=Decimal(str(prices["output"])),
                request_usd=None,
                source_url="https://platform.openai.com/docs/pricing",
            )

        # Try partial match
        for known_model, prices in self.KNOWN_MODELS.items():
            if known_model in normalized or normalized in known_model:
                return PricingResult(
                    prompt_usd_per_million=Decimal(str(prices["input"])),
                    completion_usd_per_million=Decimal(str(prices["output"])),
                    request_usd=None,
                    source_url="https://platform.openai.com/docs/pricing",
                )

        return None
