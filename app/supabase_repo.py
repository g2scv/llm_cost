"""Supabase repository layer for database operations"""

from typing import Any, Dict, List, Optional
from datetime import date, datetime
from uuid import UUID
from supabase import create_client, Client
import structlog

logger = structlog.get_logger(__name__)


class SupabaseRepo:
    """Repository for managing pricing data in Supabase"""

    def __init__(self, url: str, service_key: str):
        """
        Initialize Supabase client

        Args:
            url: Supabase project URL
            service_key: Supabase service role key
        """
        self.client: Client = create_client(url, service_key)

    # ========== Providers ==========

    def upsert_provider(
        self,
        slug: str,
        display_name: str,
        homepage_url: Optional[str] = None,
        pricing_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upsert a provider record

        Args:
            slug: Unique provider slug (e.g., 'openai')
            display_name: Provider display name
            homepage_url: Provider homepage
            pricing_url: Provider pricing page URL

        Returns:
            Upserted provider record
        """
        logger.info("upserting_provider", slug=slug)

        data = {
            "slug": slug,
            "display_name": display_name,
            "homepage_url": homepage_url,
            "pricing_url": pricing_url,
        }

        result = (
            self.client.table("providers").upsert(data, on_conflict="slug").execute()
        )

        return result.data[0] if result.data else {}

    def get_provider_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get provider by slug"""
        result = self.client.table("providers").select("*").eq("slug", slug).execute()
        return result.data[0] if result.data else None

    # ========== Models ==========

    def upsert_model(
        self,
        or_model_slug: str,
        canonical_slug: Optional[str] = None,
        display_name: Optional[str] = None,
        context_length: Optional[int] = None,
        architecture: Optional[Dict] = None,
        supported_parameters: Optional[List] = None,
    ) -> Dict[str, Any]:
        """
        Upsert a model record

        Args:
            or_model_slug: OpenRouter model slug (unique)
            canonical_slug: Canonical model slug from API
            display_name: Model display name
            context_length: Maximum context length
            architecture: Architecture metadata (JSONB)
            supported_parameters: Supported parameters list (JSONB)

        Returns:
            Upserted model record
        """
        logger.info("upserting_model", or_model_slug=or_model_slug)

        data = {
            "or_model_slug": or_model_slug,
            "canonical_slug": canonical_slug,
            "display_name": display_name,
            "context_length": context_length,
            "architecture": architecture,
            "supported_parameters": supported_parameters,
        }

        result = (
            self.client.table("models_catalog")
            .upsert(data, on_conflict="or_model_slug")
            .execute()
        )

        return result.data[0] if result.data else {}

    def get_model_by_slug(self, or_model_slug: str) -> Optional[Dict[str, Any]]:
        """Get model by OpenRouter slug"""
        result = (
            self.client.table("models_catalog")
            .select("*")
            .eq("or_model_slug", or_model_slug)
            .execute()
        )
        return result.data[0] if result.data else None

    def get_all_model_slugs(self) -> List[str]:
        """Get all known model slugs from catalog"""
        result = self.client.table("models_catalog").select("or_model_slug").execute()
        return [row["or_model_slug"] for row in result.data]

    # ========== Model-Provider Links ==========

    def link_model_provider(
        self,
        model_id: str,
        provider_id: str,
        is_top_provider: bool = False,
        provider_metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Link a model to a provider

        Args:
            model_id: UUID of the model
            provider_id: UUID of the provider
            is_top_provider: Whether this is the top provider for this model
            provider_metadata: Additional provider-specific metadata (JSONB)

        Returns:
            Link record
        """
        logger.info(
            "linking_model_provider", model_id=model_id, provider_id=provider_id
        )

        data = {
            "model_id": model_id,
            "provider_id": provider_id,
            "is_top_provider": is_top_provider,
            "provider_metadata": provider_metadata or {},
        }

        result = (
            self.client.table("model_providers")
            .upsert(data, on_conflict="model_id,provider_id")
            .execute()
        )

        return result.data[0] if result.data else {}

    def get_model_providers(self, model_id: str) -> List[Dict[str, Any]]:
        """Get all providers for a model"""
        result = (
            self.client.table("model_providers")
            .select("*, providers(*)")
            .eq("model_id", model_id)
            .execute()
        )
        return result.data

    # ========== Pricing Snapshots ==========

    def insert_pricing_snapshot(
        self,
        model_id: str,
        provider_id: Optional[str],
        snapshot_date: date,
        source_type: str,
        source_url: Optional[str] = None,
        prompt_usd_per_million: Optional[float] = None,
        completion_usd_per_million: Optional[float] = None,
        request_usd: Optional[float] = None,
        image_usd: Optional[float] = None,
        web_search_usd: Optional[float] = None,
        internal_reasoning_usd_per_million: Optional[float] = None,
        input_cache_read_usd_per_million: Optional[float] = None,
        input_cache_write_usd_per_million: Optional[float] = None,
        currency: str = "USD",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Insert a pricing snapshot (immutable history)

        Args:
            model_id: UUID of the model
            provider_id: UUID of the provider (nullable)
            snapshot_date: Date of snapshot
            source_type: 'openrouter_api' | 'provider_site' | 'web_fallback'
            source_url: URL where pricing was found
            prompt_usd_per_million: Input price per 1M tokens
            completion_usd_per_million: Output price per 1M tokens
            request_usd: Fixed per-request price
            image_usd: Image price
            web_search_usd: Web search price
            internal_reasoning_usd_per_million: Internal reasoning price per 1M tokens
            input_cache_read_usd_per_million: Cache read price per 1M tokens
            input_cache_write_usd_per_million: Cache write price per 1M tokens
            currency: Currency code (default USD)
            notes: Additional notes

        Returns:
            Inserted pricing record
        """
        logger.info(
            "inserting_pricing_snapshot",
            model_id=model_id,
            provider_id=provider_id,
            snapshot_date=snapshot_date,
            source_type=source_type,
        )

        data = {
            "model_id": model_id,
            "provider_id": provider_id,
            "snapshot_date": snapshot_date.isoformat(),
            "source_type": source_type,
            "source_url": source_url,
            "prompt_usd_per_million": prompt_usd_per_million,
            "completion_usd_per_million": completion_usd_per_million,
            "request_usd": request_usd,
            "image_usd": image_usd,
            "web_search_usd": web_search_usd,
            "internal_reasoning_usd_per_million": internal_reasoning_usd_per_million,
            "input_cache_read_usd_per_million": input_cache_read_usd_per_million,
            "input_cache_write_usd_per_million": input_cache_write_usd_per_million,
            "currency": currency,
            "notes": notes,
        }

        # Delete existing record for this combination (if any) to ensure fresh data
        # This implements the "overwrite on each run" behavior
        delete_query = (
            self.client.table("model_pricing_daily")
            .delete()
            .eq("model_id", model_id)
            .eq("snapshot_date", snapshot_date.isoformat())
            .eq("source_type", source_type)
        )

        # Handle NULL provider_id correctly
        if provider_id is None:
            delete_query = delete_query.is_("provider_id", "null")
        else:
            delete_query = delete_query.eq("provider_id", provider_id)

        delete_query.execute()

        # Insert the new snapshot
        result = self.client.table("model_pricing_daily").insert(data).execute()

        return result.data[0] if result.data else {}

    def get_latest_pricing(
        self,
        model_id: str,
        provider_id: Optional[str] = None,
        source_type: str = "openrouter_api",
    ) -> Optional[Dict[str, Any]]:
        """
        Get most recent pricing snapshot for a model (and optionally provider)

        Args:
            model_id: Model UUID
            provider_id: Provider UUID (optional)
            source_type: Source type to filter by (default: 'openrouter_api' for authoritative data)

        Returns:
            Latest pricing snapshot matching criteria
        """
        query = (
            self.client.table("model_pricing_daily")
            .select("*")
            .eq("model_id", model_id)
            .eq(
                "source_type", source_type
            )  # Filter by source to avoid comparing different sources
            .order("snapshot_date", desc=True)
            .order("collected_at", desc=True)  # Secondary sort for same-day snapshots
            .limit(1)
        )

        if provider_id:
            query = query.eq("provider_id", provider_id)
        else:
            # For OpenRouter API pricing, provider_id should be NULL
            query = query.is_("provider_id", "null")

        result = query.execute()
        return result.data[0] if result.data else None

    def get_pricing_history(
        self, model_id: str, days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get pricing history for a model"""
        result = (
            self.client.table("model_pricing_daily")
            .select("*")
            .eq("model_id", model_id)
            .order("snapshot_date", desc=True)
            .limit(days)
            .execute()
        )
        return result.data

    # ========== BYOK Verifications ==========

    def insert_byok_verification(
        self,
        model_id: str,
        provider_id: Optional[str],
        prompt_tokens: int,
        completion_tokens: int,
        openrouter_cost_usd: Optional[float],
        upstream_cost_usd: Optional[float],
        response_ms: Optional[int],
        ok: bool = True,
        raw_usage: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Insert a BYOK verification record

        Args:
            model_id: UUID of the model
            provider_id: UUID of the provider
            prompt_tokens: Tokens in prompt
            completion_tokens: Tokens in completion
            openrouter_cost_usd: OpenRouter cost from usage.cost
            upstream_cost_usd: Provider cost from usage.cost_details.upstream_inference_cost
            response_ms: Response time in milliseconds
            ok: Whether verification passed
            raw_usage: Raw usage object from response (JSONB)

        Returns:
            Inserted verification record
        """
        logger.info("inserting_byok_verification", model_id=model_id, ok=ok)

        data = {
            "model_id": model_id,
            "provider_id": provider_id,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "openrouter_cost_usd": openrouter_cost_usd,
            "upstream_cost_usd": upstream_cost_usd,
            "response_ms": response_ms,
            "ok": ok,
            "raw_usage": raw_usage or {},
        }

        result = self.client.table("byok_verifications").insert(data).execute()

        return result.data[0] if result.data else {}
