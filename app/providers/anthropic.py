"""Anthropic provider adapter using Brave Search MCP"""

from typing import Optional
from decimal import Decimal
import re
import structlog

from .base import ProviderAdapter, PricingResult

logger = structlog.get_logger(__name__)


class AnthropicAdapter(ProviderAdapter):
    """
    Adapter for Anthropic pricing using Brave Search MCP

    This adapter searches for Anthropic Claude pricing information using Brave Search
    and extracts pricing data from credible sources.
    """

    slug = "anthropic"

    # Known pricing patterns for Anthropic models (fallback if search fails)
    KNOWN_MODELS = {
        "claude-4.1-sonnet": {"input": 5.00, "output": 25.00},
        "claude-4-sonnet": {"input": 3.00, "output": 15.00},
        "claude-4.5-sonnet": {"input": 3.00, "output": 15.00},
        "claude-sonnet-4.5": {"input": 3.00, "output": 15.00},
        "claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
        "claude-3-opus": {"input": 15.00, "output": 75.00},
        "claude-4-opus": {"input": 15.00, "output": 75.00},
        "claude-4.1-opus": {"input": 15.00, "output": 75.00},
        "claude-3-sonnet": {"input": 3.00, "output": 15.00},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
        "claude-3.5-haiku": {"input": 0.80, "output": 4.00},
    }

    def __init__(self, brave_search_fn=None):
        """
        Initialize Anthropic adapter

        Args:
            brave_search_fn: Function to call Brave Search MCP (injected for testing)
        """
        self.brave_search = brave_search_fn

    async def resolve(
        self, model_name: str, model_slug: str
    ) -> Optional[PricingResult]:
        """
        Resolve Anthropic model pricing using Brave Search

        Args:
            model_name: Human-readable model name (e.g., "Claude 3.5 Sonnet")
            model_slug: OpenRouter model slug (e.g., "anthropic/claude-3.5-sonnet")

        Returns:
            PricingResult if pricing found, None otherwise
        """
        logger.info("resolving_anthropic_pricing", model=model_name, slug=model_slug)

        # Extract Anthropic model name from slug
        if "/" in model_slug:
            _, anthropic_model = model_slug.split("/", 1)
        else:
            anthropic_model = model_name.lower()

        # Try Brave Search first
        if self.brave_search:
            result = await self._search_pricing(anthropic_model, model_name)
            if result:
                return result

        # Fallback to known pricing
        result = self._get_known_pricing(anthropic_model)
        if result:
            logger.info("using_known_anthropic_pricing", model=anthropic_model)
            return result

        logger.warning("anthropic_pricing_not_found", model=anthropic_model)
        return None

    async def _search_pricing(
        self, model_name: str, display_name: str
    ) -> Optional[PricingResult]:
        """
        Search for Anthropic pricing using Brave Search

        Args:
            model_name: Anthropic model name (e.g., "claude-3.5-sonnet")
            display_name: Display name (e.g., "Claude 3.5 Sonnet")

        Returns:
            PricingResult if found in search results
        """
        if not self.brave_search:
            return None

        try:
            # Construct search query with both technical and display names
            query = f"Anthropic {display_name} API pricing per million tokens 2025"

            logger.info("searching_brave", query=query)

            # Call Brave Search
            results = await self.brave_search(query, count=5)

            # Extract pricing from search results
            prices = self._extract_prices_from_results(results)

            if prices:
                return PricingResult(
                    prompt_usd_per_million=Decimal(str(prices["input"])),
                    completion_usd_per_million=Decimal(str(prices["output"])),
                    request_usd=None,
                    source_url=prices.get(
                        "source_url", "https://www.anthropic.com/pricing"
                    ),
                )

        except Exception as e:
            logger.error("brave_search_failed", model=model_name, error=str(e))

        return None

    def _extract_prices_from_results(self, search_results: list) -> Optional[dict]:
        """
        Extract pricing from Brave Search results

        Looks for patterns like:
        - $X per million input tokens and $Y per million output tokens
        - $X (input), $Y (output) per million tokens
        - Sonnet costs $X/$Y per million tokens
        """
        # Patterns to match pricing
        patterns = [
            # "$15 per million input tokens and $75 per million output tokens"
            r"\$(\d+(?:\.\d+)?)\s*per\s+million\s+input\s+tokens?\s+and\s+\$(\d+(?:\.\d+)?)\s*per\s+million\s+output",
            # "$3 (input), $15 (output) per million tokens"
            r"\$(\d+(?:\.\d+)?)\s*\(input\)[,\s]+\$(\d+(?:\.\d+)?)\s*\(output\)",
            # "costs $3 (input), $15 (output)"
            r"costs?\s+\$(\d+(?:\.\d+)?)\s*\(input\)[,\s]+\$(\d+(?:\.\d+)?)\s*\(output\)",
            # "$3/$15 rate" or "$3-$15 per million tokens"
            r"\$(\d+(?:\.\d+)?)[/-]\$(\d+(?:\.\d+)?)\s*(?:rate|per\s+million)",
            # "Pricing... starts at $3 per million input tokens and $15 per million output tokens"
            r"starts?\s+at\s+\$(\d+(?:\.\d+)?)\s*per\s+million\s+input.*?\$(\d+(?:\.\d+)?)\s*per\s+million\s+output",
        ]

        for result in search_results:
            description = result.get("description", "")

            for pattern in patterns:
                match = re.search(pattern, description, re.IGNORECASE)
                if match:
                    input_price = float(match.group(1))
                    output_price = float(match.group(2))

                    # Validate reasonable pricing (Anthropic typically $0.25-$75 per million)
                    if 0.1 <= input_price <= 200 and 0.5 <= output_price <= 1000:
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
            model_name: Anthropic model name

        Returns:
            PricingResult if model is in known list
        """
        # Normalize model name
        normalized = model_name.lower().replace("_", "-").replace(" ", "-").strip()

        # Try exact match first
        if normalized in self.KNOWN_MODELS:
            prices = self.KNOWN_MODELS[normalized]
            return PricingResult(
                prompt_usd_per_million=Decimal(str(prices["input"])),
                completion_usd_per_million=Decimal(str(prices["output"])),
                request_usd=None,
                source_url="https://www.anthropic.com/pricing",
            )

        # Try partial match
        for known_model, prices in self.KNOWN_MODELS.items():
            if known_model in normalized or normalized in known_model:
                return PricingResult(
                    prompt_usd_per_million=Decimal(str(prices["input"])),
                    completion_usd_per_million=Decimal(str(prices["output"])),
                    request_usd=None,
                    source_url="https://www.anthropic.com/pricing",
                )

        return None
