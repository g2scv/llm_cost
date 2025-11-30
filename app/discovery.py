"""Model discovery and new model detection"""

from typing import List, Set, Dict, Any
import structlog
from bs4 import BeautifulSoup

from app.openrouter_client import OpenRouterClient
from app.supabase_repo import SupabaseRepo

logger = structlog.get_logger(__name__)


class ModelDiscovery:
    """Handles model discovery and new model detection"""

    def __init__(
        self,
        or_client: OpenRouterClient,
        repo: SupabaseRepo,
        supported_parameters_filter: str | None = None,
        distillable_filter: bool | None = None,
        input_modalities_filter: str | None = None,
        output_modalities_filter: str | None = None,
    ):
        self.or_client = or_client
        self.repo = repo
        self.supported_parameters_filter = supported_parameters_filter
        self.distillable_filter = distillable_filter
        self.input_modalities_filter = input_modalities_filter
        self.output_modalities_filter = output_modalities_filter

    def discover_models(self) -> tuple[List[Dict[str, Any]], List[str]]:
        """
        Discover models from OpenRouter API and identify new ones

        Returns:
            Tuple of (all_models, new_model_slugs)
        """
        logger.info(
            "discovering_models",
            supported_parameters=self.supported_parameters_filter,
            distillable=self.distillable_filter,
            input_modalities=self.input_modalities_filter,
            output_modalities=self.output_modalities_filter,
        )

        # Fetch models from OpenRouter with filtering
        api_models = self.or_client.list_models(
            supported_parameters=self.supported_parameters_filter,
            distillable=self.distillable_filter,
            input_modalities=self.input_modalities_filter,
            output_modalities=self.output_modalities_filter,
        )

        # Get existing models from DB
        existing_slugs = set(self.repo.get_all_model_slugs())

        # Identify new models
        api_slugs = {model.get("id", "") for model in api_models}
        new_slugs = list(api_slugs - existing_slugs)

        logger.info(
            "models_discovered",
            total=len(api_models),
            existing=len(existing_slugs),
            new=len(new_slugs),
        )

        return api_models, new_slugs

    def sync_models_to_db(self, models: List[Dict[str, Any]]) -> int:
        """
        Sync models from API to database and link to providers

        Args:
            models: List of model dicts from OpenRouter API

        Returns:
            Number of models upserted
        """
        logger.info("syncing_models_to_db", count=len(models))

        upserted = 0
        linked = 0

        for model in models:
            try:
                model_slug = model.get("id", "")

                # Upsert model
                self.repo.upsert_model(
                    or_model_slug=model_slug,
                    canonical_slug=model.get("canonical_slug"),
                    display_name=model.get("name"),
                    context_length=model.get("context_length"),
                    architecture=model.get("architecture"),
                    supported_parameters=model.get("supported_parameters"),
                )
                upserted += 1

                # Extract and link provider from model slug
                # Model slugs are like "provider/model-name" or "provider/model-name:variant"
                if "/" in model_slug:
                    provider_slug = model_slug.split("/")[0]

                    # Get model and provider records
                    model_record = self.repo.get_model_by_slug(model_slug)
                    provider_record = self.repo.get_provider_by_slug(provider_slug)

                    if model_record and provider_record:
                        # Link model to provider
                        top_provider_meta = model.get("top_provider", {})
                        self.repo.link_model_provider(
                            model_id=model_record["model_id"],
                            provider_id=provider_record["provider_id"],
                            is_top_provider=True,  # Assume the slug provider is the top provider
                            provider_metadata=top_provider_meta,
                        )
                        linked += 1
                    elif not provider_record:
                        logger.debug(
                            "provider_not_found_for_model",
                            model=model_slug,
                            provider=provider_slug,
                        )

            except Exception as e:
                logger.error(
                    "failed_to_upsert_model", model_slug=model.get("id"), error=str(e)
                )

        logger.info("models_synced", upserted=upserted, linked_to_providers=linked)
        return upserted

    def discover_providers(self) -> int:
        """
        Discover and sync providers from OpenRouter API

        Returns:
            Number of providers upserted
        """
        logger.info("discovering_providers")

        providers = self.or_client.list_providers()
        upserted = 0

        for provider in providers:
            try:
                # OpenRouter Providers API uses 'slug' field, not 'id'
                slug = provider.get("slug", "")
                name = provider.get("name", slug)

                if not slug:
                    logger.warning("provider_missing_slug", provider=provider)
                    continue

                # Extract URLs from provider data
                homepage_url = self._derive_homepage_url(provider)
                pricing_url = self._derive_pricing_url(slug, homepage_url)

                self.repo.upsert_provider(
                    slug=slug,
                    display_name=name,
                    homepage_url=homepage_url,
                    pricing_url=pricing_url,
                )
                upserted += 1

            except Exception as e:
                logger.error(
                    "failed_to_upsert_provider",
                    provider_slug=provider.get("slug"),
                    error=str(e),
                )

        logger.info("providers_synced", upserted=upserted)
        return upserted

    def _derive_homepage_url(self, provider: Dict[str, Any]) -> str | None:
        """
        Derive homepage URL from provider data

        Args:
            provider: Provider dict from OpenRouter API

        Returns:
            Homepage URL or None
        """
        from urllib.parse import urlparse

        # Try to extract homepage from privacy_policy_url, terms_of_service_url, or status_page_url
        for url_field in [
            "privacy_policy_url",
            "terms_of_service_url",
            "status_page_url",
        ]:
            url = provider.get(url_field)
            if url:
                try:
                    parsed = urlparse(url)
                    homepage = f"{parsed.scheme}://{parsed.netloc}"
                    return homepage
                except Exception:
                    continue

        return None

    def _derive_pricing_url(self, slug: str, homepage_url: str | None) -> str | None:
        """
        Derive pricing URL based on common patterns

        Args:
            slug: Provider slug
            homepage_url: Provider homepage URL

        Returns:
            Pricing URL or None
        """
        if not homepage_url:
            return None

        # Common pricing page patterns by provider
        pricing_patterns = {
            "openai": "https://openai.com/api/pricing/",
            "anthropic": "https://www.anthropic.com/pricing",
            "cohere": "https://cohere.com/pricing",
            "google": "https://ai.google.dev/pricing",
            "mistral": "https://mistral.ai/technology/#pricing",
            "groq": "https://groq.com/pricing/",
            "together": "https://www.together.ai/pricing",
            "fireworks": "https://fireworks.ai/pricing",
            "deepinfra": "https://deepinfra.com/pricing",
            "replicate": "https://replicate.com/pricing",
            "perplexity": "https://www.perplexity.ai/hub/pricing",
            "cerebras": "https://www.cerebras.ai/pricing",
        }

        # Check if we have a known pattern
        if slug in pricing_patterns:
            return pricing_patterns[slug]

        # Default fallback: try common paths
        base = homepage_url.rstrip("/")
        # Most providers use /pricing
        return f"{base}/pricing"

    def extract_providers_from_model_page(self, model_slug: str) -> List[str]:
        """
        Scrape model page to extract list of providers

        Args:
            model_slug: OpenRouter model slug (e.g., 'deepseek/deepseek-r1')

        Returns:
            List of provider slugs
        """
        logger.info("extracting_providers_from_page", model=model_slug)

        try:
            html = self.or_client.get_model_page_html(model_slug)
            soup = BeautifulSoup(html, "lxml")

            # Look for provider section
            # This is a heuristic and may need adjustment based on actual page structure
            providers = []

            # Common patterns to look for:
            # - Elements with "provider" in class name
            # - Lists of providers
            # - Provider badges/chips

            provider_elements = soup.find_all(
                class_=lambda x: x and "provider" in x.lower()
            )

            for element in provider_elements:
                # Extract text that looks like provider names
                text = element.get_text().strip()
                if text:
                    providers.append(text.lower())

            logger.info("providers_extracted", model=model_slug, count=len(providers))

            return list(set(providers))  # Deduplicate

        except Exception as e:
            logger.error("failed_to_extract_providers", model=model_slug, error=str(e))
            return []

    def link_model_providers(self, model_slug: str, provider_slugs: List[str]) -> int:
        """
        Create links between a model and its providers

        Args:
            model_slug: OpenRouter model slug
            provider_slugs: List of provider slugs

        Returns:
            Number of links created
        """
        logger.info(
            "linking_model_providers", model=model_slug, providers=provider_slugs
        )

        # Get model record
        model = self.repo.get_model_by_slug(model_slug)
        if not model:
            logger.warning("model_not_found", model_slug=model_slug)
            return 0

        model_id = model["model_id"]
        linked = 0

        for provider_slug in provider_slugs:
            # Get or create provider
            provider = self.repo.get_provider_by_slug(provider_slug)

            if not provider:
                # Provider doesn't exist yet - create minimal record
                provider = self.repo.upsert_provider(
                    slug=provider_slug, display_name=provider_slug.title()
                )

            provider_id = provider["provider_id"]

            try:
                self.repo.link_model_provider(
                    model_id=model_id, provider_id=provider_id
                )
                linked += 1

            except Exception as e:
                logger.error(
                    "failed_to_link_provider",
                    model=model_slug,
                    provider=provider_slug,
                    error=str(e),
                )

        logger.info("providers_linked", count=linked)
        return linked
