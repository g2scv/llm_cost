"""Generic web fallback scraper using Brave Search MCP"""

from typing import Optional, List
import re
from decimal import Decimal
import structlog

from .base import ProviderAdapter, PricingResult

logger = structlog.get_logger(__name__)


class GenericWebAdapter(ProviderAdapter):
    """
    Generic fallback adapter using Brave Search MCP

    This adapter:
    1. Constructs search queries for the model + provider + "pricing"
    2. Fetches top results from Brave Search
    3. Extracts pricing from trusted domains
    4. Returns the highest credible price found (as per requirements)
    """

    slug = "_generic"

    # Whitelist of credible domains for pricing info
    TRUSTED_DOMAINS = [
        "openai.com",
        "anthropic.com",
        "cohere.com",
        "ai.google.dev",
        "docs.mistral.ai",
        "mistral.ai",
        "groq.com",
        "together.ai",
        "fireworks.ai",
        "deepinfra.com",
        "replicate.com",
        "perplexity.ai",
        "openrouter.ai",
        "huggingface.co",
        "meta.com",
        "deepseek.com",
        "google.com",
        "microsoft.com",
        "azure.microsoft.com",
        "aws.amazon.com",
        "cloudzero.com",
        "metacto.com",
        "finout.io",
    ]

    def __init__(self, brave_search_fn=None):
        """
        Initialize generic web adapter

        Args:
            brave_search_fn: Function to call Brave Search MCP (injected)
        """
        self.brave_search = brave_search_fn

    async def resolve(
        self, model_name: str, model_slug: str
    ) -> Optional[PricingResult]:
        """
        Attempt to find pricing via generic web search using Brave Search MCP

        Args:
            model_name: Human-readable model name
            model_slug: OpenRouter model slug

        Returns:
            PricingResult with HIGHEST pricing found (per requirements)
        """
        if not self.brave_search:
            logger.warning(
                "brave_search_not_available",
                model=model_name,
                reason="Brave Search MCP function not injected",
            )
            return None

        logger.info("generic_web_fallback", model=model_name, slug=model_slug)

        # Extract provider and model from slug
        provider = None
        if "/" in model_slug:
            provider, short_model = model_slug.split("/", 1)
        else:
            short_model = model_name

        # Construct search queries (try multiple variations)
        queries = [
            f"{model_name} API pricing per million tokens 2025",
            f"{model_slug} pricing per million tokens",
        ]

        if provider:
            queries.insert(0, f"{provider} {short_model} API pricing 2025")

        all_prices = []

        for query in queries[:2]:  # Try top 2 queries
            try:
                logger.info("searching_brave_generic", query=query)

                results = await self.brave_search(query, count=5)

                # Extract prices from trusted sources
                prices = self._extract_all_prices_from_results(results)
                all_prices.extend(prices)

                # Early exit if we found good results
                if len(all_prices) >= 3:
                    break

            except Exception as e:
                logger.error("brave_search_failed_generic", query=query, error=str(e))

        if not all_prices:
            logger.warning("no_pricing_found_generic", model=model_name)
            return None

        # Per requirements: "get the HIGHEST pricing"
        # Pick the maximum input and output prices found
        max_input = max(p["input"] for p in all_prices)
        max_output = max(p["output"] for p in all_prices)

        # Find the source with the highest total price
        best_source = max(all_prices, key=lambda p: p["input"] + p["output"])

        logger.info(
            "generic_pricing_found",
            model=model_name,
            max_input=max_input,
            max_output=max_output,
            source=best_source["source_url"],
            total_found=len(all_prices),
        )

        return PricingResult(
            prompt_usd_per_million=Decimal(str(max_input)),
            completion_usd_per_million=Decimal(str(max_output)),
            request_usd=None,
            source_url=best_source["source_url"],
        )

    def _extract_all_prices_from_results(self, search_results: list) -> List[dict]:
        """
        Extract all pricing instances from Brave Search results

        Returns:
            List of dicts with {input, output, source_url}
        """
        all_prices = []

        # Comprehensive patterns for pricing extraction
        patterns = [
            # "$15 per million input tokens and $75 per million output tokens"
            r"\$(\d+(?:\.\d+)?)\s*per\s+million\s+input\s+tokens?\s+and\s+\$(\d+(?:\.\d+)?)\s*per\s+million\s+output",
            # "$15/MTok (input), $75/MTok (output)"
            r"\$(\d+(?:\.\d+)?)/MTok\s*\(input\)[,\s]+\$(\d+(?:\.\d+)?)/MTok\s*\(output\)",
            # "$15 (input), $75 (output) per million"
            r"\$(\d+(?:\.\d+)?)\s*\(input\)[,\s]+\$(\d+(?:\.\d+)?)\s*\(output\)",
            # "costs $15 per million input, $75 per million output"
            r"costs?\s+\$(\d+(?:\.\d+)?)\s*per\s+million\s+input[,\s]+\$(\d+(?:\.\d+)?)\s*per\s+million\s+output",
            # "$15-$75 per million tokens" or "$15/$75"
            r"\$(\d+(?:\.\d+)?)[/-]\$(\d+(?:\.\d+)?)\s*(?:per\s+million|/million)?",
            # "input: $15, output: $75"
            r"input:\s*\$(\d+(?:\.\d+)?)[,\s]+output:\s*\$(\d+(?:\.\d+)?)",
            # "starts at $15 per million input and $75 per million output"
            r"starts?\s+at\s+\$(\d+(?:\.\d+)?)\s*per\s+million\s+input.*?\$(\d+(?:\.\d+)?)\s*per\s+million\s+output",
        ]

        for result in search_results:
            # Check if source is trusted
            url = result.get("url", "")
            if not self._is_trusted_source(url):
                continue

            description = result.get("description", "")
            title = result.get("title", "")
            combined_text = f"{title} {description}"

            for pattern in patterns:
                for match in re.finditer(pattern, combined_text, re.IGNORECASE):
                    try:
                        input_price = float(match.group(1))
                        output_price = float(match.group(2))

                        # Validate reasonable pricing (most models: $0.01-$1000 per million)
                        if 0.01 <= input_price <= 1000 and 0.01 <= output_price <= 1000:
                            # Ensure output >= input (typical pattern)
                            if (
                                output_price >= input_price * 0.5
                            ):  # Allow some flexibility
                                all_prices.append(
                                    {
                                        "input": input_price,
                                        "output": output_price,
                                        "source_url": url,
                                    }
                                )
                                logger.debug(
                                    "extracted_price",
                                    input=input_price,
                                    output=output_price,
                                    source=url,
                                )
                    except (ValueError, IndexError) as e:
                        logger.debug("price_extraction_failed", error=str(e))
                        continue

        return all_prices

    def _is_trusted_source(self, url: str) -> bool:
        """
        Check if URL is from a trusted domain

        Args:
            url: URL to check

        Returns:
            True if trusted, False otherwise
        """
        url_lower = url.lower()
        return any(domain in url_lower for domain in self.TRUSTED_DOMAINS)
