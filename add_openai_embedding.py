#!/usr/bin/env python3
"""Add OpenAI text-embedding-3-large model with pricing"""

from datetime import date
from app.config import load_config
from app.supabase_repo import SupabaseRepo
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger(__name__)


def main():
    """Add text-embedding-3-large model with pricing"""

    config = load_config()
    repo = SupabaseRepo(config.supabase_url, config.supabase_service_key)

    # Model details
    model_slug = "openai/text-embedding-3-large"
    display_name = "text-embedding-3-large"

    # Pricing (you specified: $0.13 input, $0.065 output)
    # These appear to be per 1M tokens based on OpenAI's pricing
    prompt_usd_per_million = 0.13
    completion_usd_per_million = 0.065

    logger.info(
        "adding_openai_embedding_model",
        model=model_slug,
        prompt_price=prompt_usd_per_million,
        completion_price=completion_usd_per_million,
    )

    # 1. Upsert provider (OpenAI)
    provider = repo.upsert_provider(
        slug="openai",
        display_name="OpenAI",
        homepage_url="https://openai.com",
        pricing_url="https://openai.com/api/pricing/",
    )
    provider_id = provider["provider_id"]
    logger.info("upserted_provider", provider_id=provider_id)

    # 2. Upsert model
    model = repo.upsert_model(
        or_model_slug=model_slug,
        canonical_slug=model_slug,
        display_name=display_name,
        context_length=8191,  # text-embedding-3-large context length
        architecture={
            "input_modalities": ["text"],
            "output_modalities": ["embedding"],
            "model_type": "embedding",
        },
        supported_parameters=["dimensions"],
    )
    model_id = model["model_id"]
    logger.info("upserted_model", model_id=model_id)

    # 3. Link model to provider
    link = repo.link_model_provider(
        model_id=model_id,
        provider_id=provider_id,
        is_top_provider=True,
        provider_metadata={
            "embedding_dimensions": 3072,
            "max_input_tokens": 8191,
        },
    )
    logger.info("linked_model_provider", link_id=link.get("model_provider_id"))

    # 4. Insert pricing snapshot
    today = date.today()
    pricing = repo.insert_pricing_snapshot(
        model_id=model_id,
        provider_id=provider_id,
        snapshot_date=today,
        source_type="provider_site",
        source_url="https://openai.com/api/pricing/",
        prompt_usd_per_million=prompt_usd_per_million,
        completion_usd_per_million=completion_usd_per_million,
        notes="OpenAI text-embedding-3-large pricing (manually added)",
    )
    logger.info(
        "inserted_pricing",
        pricing_id=pricing.get("pricing_id"),
        snapshot_date=today,
    )

    print(f"\n✅ Successfully added {model_slug}")
    print(f"   Model ID: {model_id}")
    print(f"   Provider ID: {provider_id}")
    print(f"   Input cost: ${prompt_usd_per_million:.3f} per 1M tokens")
    print(f"   Output cost: ${completion_usd_per_million:.3f} per 1M tokens")
    print(f"   Source: https://openai.com/api/pricing/")


if __name__ == "__main__":
    main()
