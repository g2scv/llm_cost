"""Synchronization logic for updating g2scv-backend `llm_models` table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import re
from typing import Any, Dict, List, Optional

from supabase import Client, create_client
import structlog

logger = structlog.get_logger(__name__)


def _to_decimal(value: Optional[float]) -> Optional[float]:
    """Convert a float to a decimal with 6 digits of precision for storage."""

    if value is None:
        return None

    return float(Decimal(str(value)).quantize(Decimal("0.000001")))


@dataclass
class BackendModelRecord:
    """Represents a staged model ready to sync to the backend database."""

    model_id: str
    display_name: str
    provider: str
    model_type: str
    context_window: Optional[int]
    max_output_tokens: Optional[int]
    cost_per_million_input: Optional[float]
    cost_per_million_output: Optional[float]
    is_active: bool
    capabilities: Dict[str, Any]
    metadata: Dict[str, Any]
    is_thinking_model: bool
    sort_cost: float
    is_default: bool = False
    sort_order: int = 0

    def to_upsert_payload(self, now: datetime) -> Dict[str, Any]:
        """Convert the record to a Supabase upsert payload."""

        payload = {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "provider": self.provider,
            "model_type": self.model_type,
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "cost_per_million_input": _to_decimal(self.cost_per_million_input),
            "cost_per_million_output": _to_decimal(self.cost_per_million_output),
            "is_active": self.is_active,
            "is_default": self.is_default,
            "sort_order": self.sort_order,
            "capabilities": self.capabilities,
            "metadata": self.metadata,
            "is_thinking_model": self.is_thinking_model,
            "updated_at": now.isoformat(),
        }

        return payload


class BackendSupabaseRepo:
    """Repository wrapper for interacting with the g2scv-backend Supabase project."""

    def __init__(self, url: str, service_key: str):
        self.client: Client = create_client(url, service_key)

    def upsert_llm_models(self, records: List[BackendModelRecord]) -> None:
        """Upsert the provided model records into `llm_models`."""

        if not records:
            return

        now = datetime.now(timezone.utc)
        payloads = [record.to_upsert_payload(now) for record in records]

        logger.info("upserting_llm_models", count=len(payloads))
        self.client.table("llm_models").upsert(
            payloads, on_conflict="model_id"
        ).execute()

    def list_backend_model_ids(self) -> List[str]:
        """Return all model IDs currently stored in the backend table."""

        response = self.client.table("llm_models").select("model_id").execute()
        return [row["model_id"] for row in response.data or []]

    def deactivate_missing_models(self, missing_ids: List[str]) -> None:
        """Mark models as inactive if they were not part of the latest sync."""

        if not missing_ids:
            return

        now = datetime.now(timezone.utc)

        logger.info("deactivating_missing_models", count=len(missing_ids))
        self.client.table("llm_models").update(
            {"is_active": False, "is_default": False, "updated_at": now.isoformat()}
        ).in_("model_id", missing_ids).execute()


class BackendSync:
    """Coordinates staging and syncing model pricing data to the backend project."""

    # Models that should always remain active (manually added models)
    ALWAYS_ACTIVE_MODELS = {
        "openai/text-embedding-3-large",
    }

    def __init__(
        self,
        repo: Optional[BackendSupabaseRepo] = None,
        forced_defaults: Optional[Dict[str, str]] = None,
    ):
        self.repo = repo
        self.records: Dict[str, BackendModelRecord] = {}
        self.forced_defaults = forced_defaults or {}

    @property
    def enabled(self) -> bool:
        return self.repo is not None

    def stage_model(
        self, model: Dict[str, Any], normalized_pricing: Optional[Dict[str, Any]] = None
    ) -> None:
        """Stage a model for backend synchronization."""

        if not self.enabled:
            return

        model_slug = model.get("id")
        if not model_slug:
            logger.warning("backend_sync_missing_model_slug", model=model)
            return

        # Filter for pure text-to-text models only
        architecture = model.get("architecture") or {}
        input_modalities = architecture.get("input_modalities") or []
        output_modalities = architecture.get("output_modalities") or []
        
        if input_modalities != ["text"] or output_modalities != ["text"]:
            logger.debug(
                "skipping_non_text_model",
                model=model_slug,
                input_modalities=input_modalities,
                output_modalities=output_modalities,
            )
            return

        display_name = model.get("name", model_slug)
        provider = model_slug.split("/", 1)[0] if "/" in model_slug else "openrouter"

        normalized_pricing = normalized_pricing or {}

        if not normalized_pricing:
            logger.debug("skipping_model_without_pricing", model=model_slug)
            return

        prompt_price = normalized_pricing.get("prompt_usd_per_million")
        completion_price = normalized_pricing.get("completion_usd_per_million")

        # Store as per-million (no conversion needed)
        cost_per_million_input = prompt_price
        cost_per_million_output = completion_price

        # Determine if pricing indicates a free model (all known costs <= 0 or missing)
        def _is_positive(value: Optional[float]) -> bool:
            return value is not None and value > 0

        has_paid_component = any(
            _is_positive(normalized_pricing.get(key))
            for key in [
                "prompt_usd_per_million",
                "completion_usd_per_million",
                "request_usd",
                "image_usd",
                "web_search_usd",
                "internal_reasoning_usd_per_million",
                "input_cache_read_usd_per_million",
                "input_cache_write_usd_per_million",
            ]
        )

        if not has_paid_component:
            logger.info("skipping_free_model", model=model_slug)
            return

        supported_params = set(model.get("supported_parameters") or [])
        architecture = model.get("architecture") or {}
        input_modalities = architecture.get("input_modalities") or []
        output_modalities = architecture.get("output_modalities") or []

        supports_vision = "image" in input_modalities or "image" in output_modalities
        supports_audio = "audio" in input_modalities or "audio" in output_modalities
        supports_video = "video" in input_modalities or "video" in output_modalities
        supports_reasoning = (
            normalized_pricing.get("internal_reasoning_usd_per_million") is not None
            or "reasoning" in supported_params
            or "include_reasoning" in supported_params
        )

        capabilities = {
            "supports_tools": bool({"tools", "tool_choice"} & supported_params),
            "supports_vision": supports_vision,
            "supports_reasoning": supports_reasoning,
            "supports_web_search": normalized_pricing.get("web_search_usd") is not None,
            "supports_audio": supports_audio,
            "supports_video": supports_video,
        }

        if supports_reasoning:
            capabilities["supports_thinking"] = True

        model_type = self._derive_model_type(
            model_slug, display_name, supports_reasoning
        )

        context_window = model.get("context_length")
        top_provider = model.get("top_provider") or {}
        max_output_tokens = top_provider.get("max_completion_tokens")

        metadata = self._build_metadata(model, provider, cost_per_million_input)

        batch_price = normalized_pricing.get("batch_usd_per_million")
        if batch_price is not None:
            metadata["batch_usd_per_million"] = float(batch_price)

        is_active = bool(normalized_pricing)

        record = BackendModelRecord(
            model_id=model_slug,
            display_name=display_name,
            provider=provider,
            model_type=model_type,
            context_window=context_window,
            max_output_tokens=max_output_tokens,
            cost_per_million_input=cost_per_million_input,
            cost_per_million_output=cost_per_million_output,
            is_active=is_active,
            capabilities=capabilities,
            metadata=metadata,
            is_thinking_model=supports_reasoning,
            sort_cost=self._determine_sort_cost(
                cost_per_million_input, cost_per_million_output
            ),
        )

        self.records[model_slug] = record

    def finalize(self) -> None:
        """Finalize staging and push updates to the backend database."""

        if not self.enabled or not self.records:
            return

        sorted_records = sorted(
            self.records.values(),
            key=lambda r: (r.sort_cost if r.sort_cost is not None else 0.0),
            reverse=True,
        )

        for index, record in enumerate(sorted_records):
            record.sort_order = max(0, 100 - index * 5)
            record.is_default = False

        defaults_by_type: Dict[str, BackendModelRecord] = {}
        for record in sorted_records:
            if not record.is_active:
                continue

            model_type = record.model_type or "chat"
            current_default = defaults_by_type.get(model_type)

            if (
                current_default is None
                or record.sort_order > current_default.sort_order
            ):
                defaults_by_type[model_type] = record

        # Apply forced defaults (e.g., explicit chat/embedding choices)
        for model_type, model_id in self.forced_defaults.items():
            record = self.records.get(model_id)
            if not record:
                logger.warning(
                    "forced_default_missing_model",
                    model_type=model_type,
                    model_id=model_id,
                )
                continue

            if not record.is_active:
                logger.warning(
                    "forced_default_inactive",
                    model_type=model_type,
                    model_id=model_id,
                )

            defaults_by_type[model_type] = record

        for default_record in defaults_by_type.values():
            default_record.is_default = True

        self.repo.upsert_llm_models(sorted_records)

        existing_ids = set(self.repo.list_backend_model_ids())
        current_ids = set(self.records.keys())
        missing_ids = list(existing_ids - current_ids)

        # Never deactivate models in ALWAYS_ACTIVE_MODELS
        protected_missing = [
            mid for mid in missing_ids if mid in self.ALWAYS_ACTIVE_MODELS
        ]
        if protected_missing:
            logger.info(
                "skipping_deactivation_for_protected_models", models=protected_missing
            )
            missing_ids = [
                mid for mid in missing_ids if mid not in self.ALWAYS_ACTIVE_MODELS
            ]

        if missing_ids:
            self.repo.deactivate_missing_models(missing_ids)

    def _build_metadata(
        self,
        model: Dict[str, Any],
        provider: str,
        cost_per_million_input: Optional[float],
    ) -> Dict[str, Any]:
        series = self._derive_series(model.get("id"))
        description = model.get("description") or ""
        cleaned_description = self._summarize_description(description)

        metadata: Dict[str, Any] = {
            "tier": self._classify_tier(cost_per_million_input),
            "series": series,
            "provider": provider,
            "hugging_face_id": model.get("hugging_face_id"),
            "source": "openrouter",
        }

        if cleaned_description:
            metadata["description"] = cleaned_description

        return metadata

    def _classify_tier(self, cost_per_million_input: Optional[float]) -> str:
        """Classify model tier based on cost per 1M tokens"""
        if cost_per_million_input is None:
            return "experimental"

        # Thresholds adjusted for per-million pricing
        if cost_per_million_input >= 1000.0:  # Was >= 1.0 for per-1k
            return "premium"
        if cost_per_million_input >= 200.0:  # Was >= 0.2 for per-1k
            return "standard"
        return "budget"

    def _derive_series(self, model_id: Optional[str]) -> Optional[str]:
        if not model_id or "/" not in model_id:
            return None

        _, model_path = model_id.split("/", 1)
        base = model_path.split(":", 1)[0]
        segments = base.split("-")

        if len(segments) >= 2 and segments[1].replace(".", "").isdigit():
            return f"{segments[0]}-{segments[1]}"

        return segments[0] if segments else base

    def _determine_sort_cost(
        self,
        cost_per_million_input: Optional[float],
        cost_per_million_output: Optional[float],
    ) -> float:
        """Determine sort cost from per-million pricing"""
        values = [
            v
            for v in [cost_per_million_input, cost_per_million_output]
            if v is not None
        ]
        if not values:
            return 0.0
        return max(values)

    def _derive_model_type(
        self, model_slug: str, display_name: str, supports_reasoning: bool
    ) -> str:
        slug_lower = model_slug.lower()
        name_lower = display_name.lower()

        if any(keyword in slug_lower for keyword in ["embedding", "embed", "vector"]):
            return "embedding"
        if "embedding" in name_lower:
            return "embedding"
        # Backend table today only distinguishes between chat and embedding models.
        return "chat"

    def _summarize_description(self, description: str) -> Optional[str]:
        if not description:
            return None

        # Strip URLs and collapse whitespace
        no_links = re.sub(r"https?://\S+", "", description)
        normalized = re.sub(r"\s+", " ", no_links).strip()

        if not normalized:
            return None

        sentences = re.split(r"(?<=[.!?])\s+", normalized)
        lines: List[str] = []
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            lines.append(sentence)
            if len(lines) >= 2:
                break

        summary = "\n".join(lines)

        if not summary:
            return None

        # Ensure summary is not excessively long
        if len(summary) > 240:
            summary = summary[:237].rstrip() + "..."

        return summary


def build_backend_sync(
    backend_url: Optional[str],
    backend_key: Optional[str],
    forced_defaults: Optional[Dict[str, str]] = None,
) -> BackendSync:
    if not backend_url or not backend_key:
        logger.info("backend_sync_disabled", reason="missing_backend_credentials")
        return BackendSync(repo=None)

    try:
        repo = BackendSupabaseRepo(backend_url, backend_key)
        logger.info("backend_sync_enabled")
        return BackendSync(repo=repo, forced_defaults=forced_defaults)
    except Exception as exc:
        logger.error("backend_sync_initialization_failed", error=str(exc))
        return BackendSync(repo=None)
