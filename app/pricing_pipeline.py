"""Main pricing collection and orchestration pipeline"""

from typing import List, Dict, Any, Optional
from datetime import date, datetime
from decimal import Decimal
import asyncio
import structlog

from app.config import Config
from app.openrouter_client import OpenRouterClient
from app.supabase_repo import SupabaseRepo
from app.discovery import ModelDiscovery
from app.validation import PricingValidator
from app.normalize import normalize_openrouter_pricing, choose_max_pricing
from app.backend_sync import build_backend_sync
from app.providers.registry import get_adapter

logger = structlog.get_logger(__name__)


class PricingPipeline:
    """Orchestrates the complete pricing collection pipeline"""

    def __init__(self, config: Config):
        self.config = config
        self.or_client = OpenRouterClient(
            api_key=config.openrouter_api_key, timeout=config.request_timeout_seconds
        )
        self.repo = SupabaseRepo(
            url=config.supabase_url, service_key=config.supabase_service_key
        )
        self.discovery = ModelDiscovery(
            self.or_client,
            self.repo,
            supported_parameters_filter=config.model_filter_supported_parameters,
            distillable_filter=config.model_filter_distillable,
            input_modalities_filter=config.model_filter_input_modalities,
            output_modalities_filter=config.model_filter_output_modalities,
        )
        self.validator = PricingValidator(
            repo=self.repo, max_change_percent=config.price_change_threshold_percent
        )
        forced_defaults: Dict[str, str] = {}
        if config.default_chat_model_id:
            forced_defaults["chat"] = config.default_chat_model_id
        if config.default_embedding_model_id:
            forced_defaults["embedding"] = config.default_embedding_model_id

        self.backend_sync = build_backend_sync(
            config.backend_supabase_url,
            config.backend_supabase_service_key,
            forced_defaults if forced_defaults else None,
        )

    async def run_full_pipeline(self):
        """Execute the complete pricing collection pipeline"""
        logger.info("starting_pricing_pipeline")

        try:
            # Step 1: Discover and sync providers
            logger.info("step_1_discovering_providers")
            self.discovery.discover_providers()

            # Step 2: Discover and sync models
            logger.info("step_2_discovering_models")
            models, new_model_slugs = self.discovery.discover_models()
            self.discovery.sync_models_to_db(models)

            if new_model_slugs:
                logger.info("new_models_detected", count=len(new_model_slugs))

            # Step 3: Collect pricing for all models
            logger.info("step_3_collecting_pricing", model_count=len(models))
            await self._collect_pricing_for_models(models)

            # Step 4: Optional BYOK spot checks (sample a few models)
            logger.info("step_4_byok_spot_checks")
            await self._run_byok_spot_checks(models[:5])  # Check first 5 models

            logger.info("pricing_pipeline_completed")

        except Exception as e:
            logger.error("pricing_pipeline_failed", error=str(e))
            raise
        finally:
            if self.backend_sync.enabled:
                self.backend_sync.finalize()

    async def _collect_pricing_for_models(self, models: List[Dict[str, Any]]):
        """
        Collect pricing for all models

        Args:
            models: List of model dicts from OpenRouter API
        """
        today = date.today()
        concurrency = max(1, self.config.max_parallel_models)
        semaphore = asyncio.Semaphore(concurrency)

        async def process_model(model: Dict[str, Any]) -> None:
            async with semaphore:
                try:
                    await self._collect_pricing_for_model(model, today)
                except Exception as e:
                    logger.error(
                        "failed_to_collect_pricing_for_model",
                        model=model.get("id"),
                        error=str(e),
                    )

        tasks = [asyncio.create_task(process_model(model)) for model in models]
        if tasks:
            await asyncio.gather(*tasks)

    async def _collect_pricing_for_model(
        self, model: Dict[str, Any], snapshot_date: date
    ):
        """
        Collect pricing for a single model

        Strategy:
        1. Try OpenRouter API pricing (baseline)
        2. Try provider-specific adapters
        3. Fall back to generic web search

        For each provider, choose the maximum price if multiple found
        """
        model_slug = model.get("id", "")
        model_name = model.get("name", "")

        logger.info("collecting_pricing", model=model_slug)

        # Get model record from DB
        model_record = self.repo.get_model_by_slug(model_slug)
        if not model_record:
            logger.error("model_not_in_db", model=model_slug)
            return

        model_id = model_record["model_id"]

        normalized_pricing = None

        # Step 1: Collect from OpenRouter API
        if "pricing" in model:
            normalized_pricing = await self._store_openrouter_pricing(
                model_id, model["pricing"], snapshot_date, model_slug
            )

        # Step 2: Collect from providers (optional, can be disabled to avoid rate limits)
        if self.config.enable_provider_scraping:
            # Get linked providers for this model
            model_providers = self.repo.get_model_providers(model_id)

            for mp in model_providers:
                provider = mp.get("providers")
                if not provider:
                    continue

                provider_id = provider["provider_id"]
                provider_slug = provider["slug"]

                await self._collect_provider_pricing(
                    model_id,
                    provider_id,
                    provider_slug,
                    model_name,
                    model_slug,
                    snapshot_date,
                )
        else:
            logger.debug("provider_scraping_disabled", model=model_slug)

        if self.backend_sync.enabled:
            self.backend_sync.stage_model(model, normalized_pricing)

    async def _store_openrouter_pricing(
        self,
        model_id: str,
        pricing: Dict[str, Any],
        snapshot_date: date,
        model_slug: str,
    ):
        """Store pricing from OpenRouter API"""
        logger.info("storing_openrouter_pricing", model=model_slug)

        # Normalize pricing
        normalized = normalize_openrouter_pricing(pricing)

        # Override known curated pricing for specific models
        if model_slug == "text-embedding-3-large":
            normalized["prompt_usd_per_million"] = Decimal("0.13")
            normalized["completion_usd_per_million"] = None
            normalized["batch_usd_per_million"] = Decimal("0.065")
            normalized["notes"] = "OpenAI published pricing"

        # Validate
        prompt_price = normalized.get("prompt_usd_per_million")
        completion_price = normalized.get("completion_usd_per_million")

        # Skip storing if pricing is invalid (e.g., negative sentinel values)
        if prompt_price is None and completion_price is None:
            logger.debug(
                "skipping_invalid_pricing",
                model=model_slug,
                msg="No valid pricing available (likely dynamic routing or unavailable)",
            )
            return None

        # Check if model has image pricing (affects validation)
        has_image_pricing = pricing.get("image") is not None

        is_valid, warnings = self.validator.validate_pricing(
            prompt_price,
            completion_price,
            model_slug=model_slug,
            has_image_pricing=has_image_pricing,
        )

        if not is_valid:
            logger.warning(
                "openrouter_pricing_validation_failed",
                model=model_slug,
                warnings=warnings,
            )
            # Don't store invalid pricing
            return None

        # Check for significant changes
        alert, changes = self.validator.check_price_change(
            model_id,
            None,  # No specific provider for OpenRouter baseline
            prompt_price,
            completion_price,
        )

        # Store snapshot (convert Decimal to float)
        normalized_floats = {
            k: float(v) if isinstance(v, Decimal) else v for k, v in normalized.items()
        }

        self.repo.insert_pricing_snapshot(
            model_id=model_id,
            provider_id=None,  # OpenRouter aggregate pricing
            snapshot_date=snapshot_date,
            source_type="openrouter_api",
            source_url="https://openrouter.ai/api/v1/models",
            **normalized_floats,
            notes="Warnings: " + "; ".join(warnings) if warnings else None,
        )

        logger.info("openrouter_pricing_stored", model=model_slug)

        return normalized_floats

    async def _collect_provider_pricing(
        self,
        model_id: str,
        provider_id: str,
        provider_slug: str,
        model_name: str,
        model_slug: str,
        snapshot_date: date,
    ):
        """Collect pricing from a specific provider"""
        logger.info(
            "collecting_provider_pricing", model=model_slug, provider=provider_slug
        )

        # Get provider adapter with Brave API key
        adapter = get_adapter(provider_slug, brave_api_key=self.config.brave_api_key)

        try:
            # Resolve pricing using adapter
            result = await adapter.resolve(model_name, model_slug)

            if result:
                # Validate
                is_valid, warnings = self.validator.validate_pricing(
                    result.prompt_usd_per_million,
                    result.completion_usd_per_million,
                    model_slug=model_slug,
                    has_image_pricing=False,  # Provider adapters don't scrape image pricing
                )

                # Check for changes
                alert, changes = self.validator.check_price_change(
                    model_id,
                    provider_id,
                    result.prompt_usd_per_million,
                    result.completion_usd_per_million,
                )

                # Store snapshot
                self.repo.insert_pricing_snapshot(
                    model_id=model_id,
                    provider_id=provider_id,
                    snapshot_date=snapshot_date,
                    source_type="provider_site",
                    source_url=result.source_url,
                    prompt_usd_per_million=float(result.prompt_usd_per_million)
                    if result.prompt_usd_per_million
                    else None,
                    completion_usd_per_million=float(result.completion_usd_per_million)
                    if result.completion_usd_per_million
                    else None,
                    request_usd=float(result.request_usd)
                    if result.request_usd
                    else None,
                    notes=result.notes,
                )

                logger.info(
                    "provider_pricing_stored", model=model_slug, provider=provider_slug
                )
            else:
                logger.info(
                    "provider_pricing_not_found",
                    model=model_slug,
                    provider=provider_slug,
                )

        except Exception as e:
            logger.error(
                "provider_pricing_collection_failed",
                model=model_slug,
                provider=provider_slug,
                error=str(e),
            )

    async def _run_byok_spot_checks(self, models: List[Dict[str, Any]]):
        """
        Run BYOK spot checks on a sample of models

        Args:
            models: Sample of models to check
        """
        logger.info("running_byok_spot_checks", count=len(models))

        # Filter out models with no pricing (likely deprecated/removed)
        valid_models = []
        for model in models:
            pricing = model.get("pricing", {})
            prompt_price = pricing.get("prompt")
            completion_price = pricing.get("completion")

            # Skip models with missing pricing or sentinel values
            if prompt_price in [None, "0", 0, "-1", -1] and completion_price in [
                None,
                "0",
                0,
                "-1",
                -1,
            ]:
                logger.debug(
                    "skipping_byok_for_free_or_unavailable_model", model=model.get("id")
                )
                continue

            valid_models.append(model)

        logger.info(
            "byok_spot_checks_filtered", total=len(models), valid=len(valid_models)
        )

        for model in valid_models:
            try:
                await self._run_byok_spot_check(model)
            except Exception as e:
                logger.error(
                    "byok_spot_check_failed", model=model.get("id"), error=str(e)
                )

    async def _run_byok_spot_check(self, model: Dict[str, Any]):
        """Run a BYOK spot check for a single model"""
        model_slug = model.get("id", "")

        logger.info("byok_spot_check", model=model_slug)

        try:
            # Make tiny request with usage tracking
            response = self.or_client.tiny_byok_call(model_slug)

            usage = response.get("usage", {})

            if not usage:
                logger.warning("no_usage_data", model=model_slug)
                return

            # Get model record
            model_record = self.repo.get_model_by_slug(model_slug)
            if not model_record:
                return

            model_id = model_record["model_id"]

            # Extract usage details
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            cost = usage.get("cost", 0)
            upstream_cost = usage.get("cost_details", {}).get(
                "upstream_inference_cost", 0
            )

            # Store verification
            self.repo.insert_byok_verification(
                model_id=model_id,
                provider_id=None,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                openrouter_cost_usd=cost,
                upstream_cost_usd=upstream_cost,
                response_ms=None,
                ok=True,
                raw_usage=usage,
            )

            logger.info(
                "byok_spot_check_completed",
                model=model_slug,
                cost=cost,
                upstream_cost=upstream_cost,
            )

        except Exception as e:
            logger.error("byok_spot_check_error", model=model_slug, error=str(e))


async def run_once(config: Config):
    """Run the pricing pipeline once"""
    pipeline = PricingPipeline(config)
    await pipeline.run_full_pipeline()
