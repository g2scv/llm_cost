"""Unit tests for provider pricing adapters."""

from decimal import Decimal
import pytest

from app.providers.openai import OpenAIAdapter
from app.providers.anthropic import AnthropicAdapter
from app.providers.generic_web import GenericWebAdapter


@pytest.mark.asyncio
async def test_openai_adapter_returns_known_pricing() -> None:
    adapter = OpenAIAdapter()

    result = await adapter.resolve("GPT-4o", "openai/gpt-4o")

    assert result is not None
    assert result.prompt_usd_per_million == Decimal("2.5")
    assert result.completion_usd_per_million == Decimal("10.0")
    assert "openai.com" in result.source_url


@pytest.mark.asyncio
async def test_anthropic_adapter_returns_known_pricing() -> None:
    adapter = AnthropicAdapter()

    result = await adapter.resolve("Claude 3.5 Sonnet", "anthropic/claude-3.5-sonnet")

    assert result is not None
    assert result.prompt_usd_per_million == Decimal("3.0")
    assert result.completion_usd_per_million == Decimal("15.0")
    assert "anthropic.com" in result.source_url


@pytest.mark.asyncio
async def test_generic_adapter_extracts_highest_pricing() -> None:
    async def fake_brave_search(query: str, count: int = 5) -> list:
        return [
            {
                "title": "Pricing Overview",
                "url": "https://openai.com/pricing",
                "description": "$1 per million input tokens and $2 per million output tokens",
            },
            {
                "title": "Detailed Pricing",
                "url": "https://anthropic.com/pricing",
                "description": "$3 per million input tokens and $6 per million output tokens",
            },
        ]

    adapter = GenericWebAdapter(brave_search_fn=fake_brave_search)

    result = await adapter.resolve("Test Model", "openai/test-model")

    assert result is not None
    assert result.prompt_usd_per_million == Decimal("3")
    assert result.completion_usd_per_million == Decimal("6")
    assert "pricing" in result.source_url
