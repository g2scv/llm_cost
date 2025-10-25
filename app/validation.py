"""Validation and sanity checks for pricing data"""

from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import date, timedelta
import structlog

from app.supabase_repo import SupabaseRepo
from app.normalize import calculate_price_change_percent, is_price_reasonable

logger = structlog.get_logger(__name__)


class PricingValidator:
    """Validates pricing data for sanity and alerts on anomalies"""

    def __init__(
        self,
        repo: SupabaseRepo,
        max_change_percent: float = 30.0,
        min_price: Decimal = Decimal("0.0"),
        max_price: Decimal = Decimal("1000.0"),
    ):
        """
        Initialize validator

        Args:
            repo: Supabase repository
            max_change_percent: Alert threshold for price changes
            min_price: Minimum reasonable price per 1M tokens
            max_price: Maximum reasonable price per 1M tokens
        """
        self.repo = repo
        self.max_change_percent = max_change_percent
        self.min_price = min_price
        self.max_price = max_price

    def validate_pricing(
        self,
        prompt_price: Optional[Decimal],
        completion_price: Optional[Decimal],
        model_slug: Optional[str] = None,
        has_image_pricing: bool = False,
    ) -> tuple[bool, list[str]]:
        """
        Validate that prices are reasonable

        Args:
            prompt_price: Prompt price per 1M tokens
            completion_price: Completion price per 1M tokens
            model_slug: Model slug for context (optional)
            has_image_pricing: Whether model has image pricing (affects validation)

        Returns:
            Tuple of (is_valid, list_of_warnings)
        """
        warnings = []

        # Check if prices are within reasonable bounds
        if not is_price_reasonable(
            prompt_price, completion_price, self.min_price, self.max_price
        ):
            warnings.append(
                f"Price outside reasonable range [{self.min_price}, {self.max_price}]"
            )

        # Check if prices are non-negative
        if prompt_price is not None and prompt_price < 0:
            warnings.append(f"Negative prompt price: {prompt_price}")

        if completion_price is not None and completion_price < 0:
            warnings.append(f"Negative completion price: {completion_price}")

        # Check if completion is typically more expensive than prompt
        # EXCEPTION: Image models (e.g., gpt-5-image-mini) may have lower completion costs
        if (
            prompt_price is not None
            and completion_price is not None
            and completion_price < prompt_price
            and not has_image_pricing  # Skip warning for image models
        ):
            logger.debug(
                "completion_less_than_prompt",
                model=model_slug,
                prompt=prompt_price,
                completion=completion_price,
                msg="Unusual but valid for some models (e.g., image models)",
            )

        is_valid = len(warnings) == 0

        if not is_valid:
            logger.warning(
                "pricing_validation_warnings",
                model=model_slug,
                prompt=prompt_price,
                completion=completion_price,
                warnings=warnings,
            )

        return is_valid, warnings

    def check_price_change(
        self,
        model_id: str,
        provider_id: Optional[str],
        new_prompt_price: Optional[Decimal],
        new_completion_price: Optional[Decimal],
    ) -> tuple[bool, Dict[str, Any]]:
        """
        Check if price has changed significantly since last snapshot

        Args:
            model_id: Model UUID
            provider_id: Provider UUID (optional)
            new_prompt_price: New prompt price
            new_completion_price: New completion price

        Returns:
            Tuple of (alert_needed, change_details)
        """
        # Get most recent pricing
        latest = self.repo.get_latest_pricing(model_id, provider_id)

        if not latest:
            # No previous pricing to compare
            return False, {"reason": "no_previous_pricing"}

        old_prompt = latest.get("prompt_usd_per_million")
        old_completion = latest.get("completion_usd_per_million")

        if old_prompt:
            old_prompt = Decimal(str(old_prompt))
        if old_completion:
            old_completion = Decimal(str(old_completion))

        changes = {}
        alert_needed = False

        # Check prompt price change
        if old_prompt is not None and new_prompt_price is not None:
            prompt_change = calculate_price_change_percent(old_prompt, new_prompt_price)

            if prompt_change is not None:
                changes["prompt_change_percent"] = float(prompt_change)

                if abs(prompt_change) > Decimal(str(self.max_change_percent)):
                    alert_needed = True
                    changes["prompt_alert"] = True

        # Check completion price change
        if old_completion is not None and new_completion_price is not None:
            completion_change = calculate_price_change_percent(
                old_completion, new_completion_price
            )

            if completion_change is not None:
                changes["completion_change_percent"] = float(completion_change)

                if abs(completion_change) > Decimal(str(self.max_change_percent)):
                    alert_needed = True
                    changes["completion_alert"] = True

        if alert_needed:
            logger.warning(
                "significant_price_change_detected",
                model_id=model_id,
                provider_id=provider_id,
                old_prompt=old_prompt,
                new_prompt=new_prompt_price,
                old_completion=old_completion,
                new_completion=new_completion_price,
                changes=changes,
            )

        return alert_needed, changes

    def validate_byok_verification(
        self, usage_data: Dict[str, Any], is_byok: bool, monthly_byok_requests: int
    ) -> tuple[bool, list[str]]:
        """
        Validate BYOK verification results

        Args:
            usage_data: Usage data from OpenRouter response
            is_byok: Whether this is a BYOK request
            monthly_byok_requests: Current month's BYOK request count

        Returns:
            Tuple of (is_valid, list_of_warnings)
        """
        warnings = []

        cost = usage_data.get("cost", 0)
        upstream_cost = usage_data.get("cost_details", {}).get(
            "upstream_inference_cost", 0
        )

        if is_byok:
            # First 1M requests should be free
            if monthly_byok_requests < 1_000_000:
                if cost != 0:
                    warnings.append(
                        f"Expected free BYOK (request #{monthly_byok_requests}), "
                        f"but cost={cost}"
                    )
            else:
                # After 1M, should be ~5% of upstream cost
                expected_cost = upstream_cost * 0.05
                tolerance = 0.01  # 1 cent tolerance

                if abs(cost - expected_cost) > tolerance:
                    warnings.append(
                        f"BYOK cost mismatch: expected ~{expected_cost:.4f} "
                        f"(5% of {upstream_cost}), got {cost}"
                    )

        is_valid = len(warnings) == 0

        if not is_valid:
            logger.warning(
                "byok_validation_warnings", usage=usage_data, warnings=warnings
            )

        return is_valid, warnings
