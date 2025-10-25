"""Provider adapter registry with Brave Search MCP integration"""

from typing import Dict, Optional, Callable, Any
import structlog
import httpx
import json

from .base import ProviderAdapter
from .openai import OpenAIAdapter
from .anthropic import AnthropicAdapter
from .google import GoogleAdapter
from .cohere import CohereAdapter
from .mistral import MistralAdapter
from .deepseek import DeepSeekAdapter
from .groq import GroqAdapter
from .together import TogetherAdapter
from .fireworks import FireworksAdapter
from .deepinfra import DeepInfraAdapter
from .generic_web import GenericWebAdapter

logger = structlog.get_logger(__name__)


async def brave_search_wrapper(query: str, count: int = 5, api_key: str = None) -> list:
    """
    Wrapper for Brave Search MCP

    This function calls the Brave Search API directly since MCP functions
    are not importable in the traditional Python way.

    Args:
        query: Search query
        count: Number of results
        api_key: Brave API key (optional, will try to get from env if not provided)

    Returns:
        List of search results
    """
    try:
        # Try to get API key from parameter first, then environment
        import os

        brave_api_key = api_key or os.getenv("BRAVE_API_KEY")

        if not brave_api_key:
            logger.warning(
                "brave_api_key_not_set",
                msg="Set BRAVE_API_KEY env var for web scraping",
            )
            return []

        # Add delay to respect rate limits
        import asyncio

        await asyncio.sleep(1.0)  # 1 second delay between requests

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": brave_api_key,
                },
                params={"q": query, "count": count},
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get("web", {}).get("results", [])

                # Convert to format expected by adapters
                formatted_results = []
                for result in results:
                    formatted_results.append(
                        {
                            "title": result.get("title", ""),
                            "url": result.get("url", ""),
                            "description": result.get("description", ""),
                        }
                    )

                logger.info(
                    "brave_search_success", query=query, results=len(formatted_results)
                )
                return formatted_results
            else:
                logger.error(
                    "brave_search_api_error", status=response.status_code, query=query
                )
                return []

    except Exception as e:
        logger.error("brave_search_failed", query=query, error=str(e))
        return []


class ProviderRegistry:
    """Registry of provider adapters with Brave Search integration"""

    def __init__(self, brave_search_fn: Optional[Callable] = None):
        """
        Initialize registry

        Args:
            brave_search_fn: Function to use for Brave Search (defaults to brave_search_wrapper)
        """
        self._adapters: Dict[str, ProviderAdapter] = {}
        self._brave_search_fn = brave_search_fn or brave_search_wrapper

        # Create adapters with Brave Search injected
        self._generic_adapter = GenericWebAdapter(brave_search_fn=self._brave_search_fn)

        # Register all known provider adapters with Brave Search
        self.register(OpenAIAdapter(brave_search_fn=self._brave_search_fn))
        self.register(AnthropicAdapter(brave_search_fn=self._brave_search_fn))
        self.register(GoogleAdapter(brave_search_fn=self._brave_search_fn))
        self.register(CohereAdapter(brave_search_fn=self._brave_search_fn))
        self.register(MistralAdapter(brave_search_fn=self._brave_search_fn))
        self.register(DeepSeekAdapter(brave_search_fn=self._brave_search_fn))
        self.register(GroqAdapter(brave_search_fn=self._brave_search_fn))
        self.register(TogetherAdapter(brave_search_fn=self._brave_search_fn))
        self.register(FireworksAdapter(brave_search_fn=self._brave_search_fn))
        self.register(DeepInfraAdapter(brave_search_fn=self._brave_search_fn))

    def register(self, adapter: ProviderAdapter):
        """Register a provider adapter"""
        self._adapters[adapter.slug] = adapter
        logger.info("registered_provider_adapter", slug=adapter.slug)

    def get(self, provider_slug: str) -> ProviderAdapter:
        """
        Get adapter for a provider slug

        Falls back to generic adapter if specific adapter not found
        """
        adapter = self._adapters.get(provider_slug)

        if adapter:
            logger.debug("using_specific_adapter", slug=provider_slug)
            return adapter
        else:
            logger.debug("using_generic_adapter", slug=provider_slug)
            return self._generic_adapter

    def list_adapters(self) -> list[str]:
        """List all registered adapter slugs"""
        return list(self._adapters.keys())


# Global registry instance with Brave Search
registry = ProviderRegistry()


def get_adapter(provider_slug: str, brave_api_key: str = None) -> ProviderAdapter:
    """
    Convenience function to get an adapter from the global registry

    Args:
        provider_slug: Provider slug
        brave_api_key: Brave API key (optional)

    Returns:
        Provider adapter
    """
    if brave_api_key:
        # Create a search function with API key bound
        async def search_with_key(query: str, count: int = 5) -> list:
            return await brave_search_wrapper(query, count, api_key=brave_api_key)

        # Create new registry with bound search function
        temp_registry = ProviderRegistry(brave_search_fn=search_with_key)
        return temp_registry.get(provider_slug)
    else:
        return registry.get(provider_slug)


def get_adapter_with_search(
    provider_slug: str, brave_search_fn: Optional[Callable] = None
) -> ProviderAdapter:
    """
    Get an adapter with custom Brave Search function

    Args:
        provider_slug: Provider slug
        brave_search_fn: Custom Brave Search function (optional)

    Returns:
        Provider adapter with search enabled
    """
    if brave_search_fn:
        # Create a new registry with custom search function
        custom_registry = ProviderRegistry(brave_search_fn=brave_search_fn)
        return custom_registry.get(provider_slug)
    else:
        return get_adapter(provider_slug)
