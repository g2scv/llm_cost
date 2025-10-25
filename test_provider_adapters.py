#!/usr/bin/env python3
"""Test script for provider adapters"""

import asyncio
import os
from app.providers.openai import OpenAIAdapter
from app.providers.anthropic import AnthropicAdapter
from app.providers.generic_web import GenericWebAdapter
from app.providers.registry import brave_search_wrapper


async def test_openai_adapter():
    """Test OpenAI adapter"""
    print("\n" + "=" * 60)
    print("Testing OpenAI Adapter")
    print("=" * 60)

    adapter = OpenAIAdapter(brave_search_fn=brave_search_wrapper)

    test_models = [
        ("GPT-4o", "openai/gpt-4o"),
        ("GPT-4o Mini", "openai/gpt-4o-mini"),
        ("GPT-3.5 Turbo", "openai/gpt-3.5-turbo"),
    ]

    for name, slug in test_models:
        print(f"\nTesting: {name} ({slug})")
        result = await adapter.resolve(name, slug)

        if result:
            print(f"  ✅ Found pricing:")
            print(f"     Input:  ${result.prompt_usd_per_million}/1M tokens")
            print(f"     Output: ${result.completion_usd_per_million}/1M tokens")
            print(f"     Source: {result.source_url}")
        else:
            print(f"  ❌ No pricing found")


async def test_anthropic_adapter():
    """Test Anthropic adapter"""
    print("\n" + "=" * 60)
    print("Testing Anthropic Adapter")
    print("=" * 60)

    adapter = AnthropicAdapter(brave_search_fn=brave_search_wrapper)

    test_models = [
        ("Claude 3.5 Sonnet", "anthropic/claude-3.5-sonnet"),
        ("Claude 4 Opus", "anthropic/claude-4-opus"),
        ("Claude 3 Haiku", "anthropic/claude-3-haiku"),
    ]

    for name, slug in test_models:
        print(f"\nTesting: {name} ({slug})")
        result = await adapter.resolve(name, slug)

        if result:
            print(f"  ✅ Found pricing:")
            print(f"     Input:  ${result.prompt_usd_per_million}/1M tokens")
            print(f"     Output: ${result.completion_usd_per_million}/1M tokens")
            print(f"     Source: {result.source_url}")
        else:
            print(f"  ❌ No pricing found")


async def test_generic_adapter():
    """Test generic web adapter"""
    print("\n" + "=" * 60)
    print("Testing Generic Web Adapter")
    print("=" * 60)

    adapter = GenericWebAdapter(brave_search_fn=brave_search_wrapper)

    test_models = [
        ("Mistral Large", "mistralai/mistral-large"),
        ("Google Gemini Pro", "google/gemini-pro"),
        ("Cohere Command R+", "cohere/command-r-plus"),
    ]

    for name, slug in test_models:
        print(f"\nTesting: {name} ({slug})")
        result = await adapter.resolve(name, slug)

        if result:
            print(f"  ✅ Found pricing:")
            print(f"     Input:  ${result.prompt_usd_per_million}/1M tokens")
            print(f"     Output: ${result.completion_usd_per_million}/1M tokens")
            print(f"     Source: {result.source_url}")
        else:
            print(f"  ❌ No pricing found")


async def test_brave_search():
    """Test Brave Search wrapper"""
    print("\n" + "=" * 60)
    print("Testing Brave Search Wrapper")
    print("=" * 60)

    brave_api_key = os.getenv("BRAVE_API_KEY")

    if not brave_api_key:
        print("\n⚠️  BRAVE_API_KEY not set in environment")
        print("   Set it to enable web scraping:")
        print("   export BRAVE_API_KEY=your_key_here")
        print(
            "\n   Adapters will fall back to known pricing if Brave is not available."
        )
        return

    print(f"\n✅ Brave API Key configured: {brave_api_key[:10]}...")

    # Test search
    query = "OpenAI GPT-4o pricing per million tokens 2025"
    print(f"\nSearching: {query}")

    results = await brave_search_wrapper(query, count=3)

    if results:
        print(f"\n✅ Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['title']}")
            print(f"   URL: {result['url']}")
            print(f"   Description: {result['description'][:100]}...")
    else:
        print("\n❌ No results returned")


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("🧪 Provider Adapter Test Suite")
    print("=" * 60)

    # Test Brave Search first
    await test_brave_search()

    # Test each adapter
    await test_openai_adapter()
    await test_anthropic_adapter()
    await test_generic_adapter()

    print("\n" + "=" * 60)
    print("✅ Test suite completed!")
    print("=" * 60)
    print("\nNotes:")
    print("- If Brave API is not configured, adapters use fallback pricing")
    print("- Fallback pricing is based on known model prices")
    print("- For production, set BRAVE_API_KEY for real-time web pricing")
    print()


if __name__ == "__main__":
    asyncio.run(main())
