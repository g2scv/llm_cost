"""Price normalization utilities - convert various units to USD per 1M tokens"""

from decimal import Decimal, InvalidOperation
from typing import Optional, Union
import structlog

logger = structlog.get_logger(__name__)

NumericType = Union[int, float, str, Decimal]


def to_decimal(value: Optional[NumericType]) -> Optional[Decimal]:
    """
    Safely convert a value to Decimal

    Args:
        value: Numeric value (int, float, str, or Decimal)

    Returns:
        Decimal or None if conversion fails
    """
    if value is None:
        return None

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as e:
        logger.warning("decimal_conversion_failed", value=value, error=str(e))
        return None


def per_token_to_per1m(value: Optional[NumericType]) -> Optional[Decimal]:
    """
    Convert per-token price to per-1M tokens

    Special handling:
    - Returns None for negative values (e.g., -1 for dynamic pricing)
    - Returns None for zero values (free models)

    Args:
        value: Price per token

    Returns:
        Price per 1M tokens as Decimal, or None for sentinel values

    Example:
        >>> per_token_to_per1m(0.000003)
        Decimal('3.0')
        >>> per_token_to_per1m(-1)  # Sentinel for dynamic pricing
        None
        >>> per_token_to_per1m(0)  # Free model
        Decimal('0.0')
    """
    decimal_value = to_decimal(value)
    if decimal_value is None:
        return None

    # Handle sentinel values (negative numbers indicate dynamic/special pricing)
    if decimal_value < 0:
        logger.debug(
            "sentinel_pricing_value",
            value=value,
            msg="Negative price indicates dynamic routing or unavailable",
        )
        return None

    return decimal_value * Decimal("1000000")


def per1k_to_per1m(value: Optional[NumericType]) -> Optional[Decimal]:
    """
    Convert per-1K tokens price to per-1M tokens

    Args:
        value: Price per 1K tokens

    Returns:
        Price per 1M tokens as Decimal

    Example:
        >>> per1k_to_per1m(3.0)
        Decimal('3000.0')
    """
    decimal_value = to_decimal(value)
    if decimal_value is None:
        return None

    return decimal_value * Decimal("1000")


def per1m_passthrough(value: Optional[NumericType]) -> Optional[Decimal]:
    """
    Pass through per-1M value (just convert to Decimal)

    Args:
        value: Price per 1M tokens

    Returns:
        Same price as Decimal
    """
    return to_decimal(value)


def normalize_openrouter_pricing(pricing: dict) -> dict:
    """
    Normalize OpenRouter API pricing object to per-1M USD

    OpenRouter pricing fields are in USD per token/request, so we need to
    multiply token-based fields by 1M.

    Args:
        pricing: Pricing dict from OpenRouter Models API

    Returns:
        Normalized pricing dict with per-1M values

    Example:
        >>> pricing = {"prompt": "0.000003", "completion": "0.000015"}
        >>> normalize_openrouter_pricing(pricing)
        {
            'prompt_usd_per_million': Decimal('3.0'),
            'completion_usd_per_million': Decimal('15.0'),
            ...
        }
    """
    result = {}

    # Token-based pricing (multiply by 1M)
    if "prompt" in pricing:
        result["prompt_usd_per_million"] = per_token_to_per1m(pricing["prompt"])

    if "completion" in pricing:
        result["completion_usd_per_million"] = per_token_to_per1m(pricing["completion"])

    if "internal_reasoning" in pricing:
        result["internal_reasoning_usd_per_million"] = per_token_to_per1m(
            pricing["internal_reasoning"]
        )

    if "input_cache_read" in pricing:
        result["input_cache_read_usd_per_million"] = per_token_to_per1m(
            pricing["input_cache_read"]
        )

    if "input_cache_write" in pricing:
        result["input_cache_write_usd_per_million"] = per_token_to_per1m(
            pricing["input_cache_write"]
        )

    # Per-request pricing (no conversion needed)
    if "request" in pricing:
        result["request_usd"] = to_decimal(pricing["request"])

    if "image" in pricing:
        result["image_usd"] = to_decimal(pricing["image"])

    if "web_search" in pricing:
        result["web_search_usd"] = to_decimal(pricing["web_search"])

    logger.debug("normalized_openrouter_pricing", original=pricing, normalized=result)

    return result


def choose_max_pricing(pricing_options: list[dict]) -> dict:
    """
    Choose maximum prices from multiple pricing options

    When a provider has multiple tiers/regions, we want the highest price
    according to the spec.

    Args:
        pricing_options: List of normalized pricing dicts

    Returns:
        Dict with maximum value for each pricing field

    Example:
        >>> options = [
        ...     {'prompt_usd_per_million': Decimal('3.0')},
        ...     {'prompt_usd_per_million': Decimal('5.0')}
        ... ]
        >>> choose_max_pricing(options)
        {'prompt_usd_per_million': Decimal('5.0')}
    """
    if not pricing_options:
        return {}

    # Collect all unique keys
    all_keys = set()
    for option in pricing_options:
        all_keys.update(option.keys())

    result = {}

    for key in all_keys:
        # Filter out None values and get max
        values = [
            option[key]
            for option in pricing_options
            if key in option and option[key] is not None
        ]

        if values:
            result[key] = max(values)

    logger.debug("chose_max_pricing", num_options=len(pricing_options), result=result)

    return result


def is_price_reasonable(
    prompt_price: Optional[Decimal],
    completion_price: Optional[Decimal],
    min_price: Decimal = Decimal("0.0"),
    max_price: Decimal = Decimal("1000.0"),
) -> bool:
    """
    Sanity check if prices are within reasonable bounds

    Args:
        prompt_price: Prompt price per 1M tokens
        completion_price: Completion price per 1M tokens
        min_price: Minimum reasonable price (default 0)
        max_price: Maximum reasonable price (default $1000 per 1M)

    Returns:
        True if prices are reasonable
    """
    if prompt_price is not None:
        if not (min_price <= prompt_price <= max_price):
            logger.warning(
                "unreasonable_prompt_price",
                price=prompt_price,
                min=min_price,
                max=max_price,
            )
            return False

    if completion_price is not None:
        if not (min_price <= completion_price <= max_price):
            logger.warning(
                "unreasonable_completion_price",
                price=completion_price,
                min=min_price,
                max=max_price,
            )
            return False

    return True


def calculate_price_change_percent(
    old_price: Optional[Decimal], new_price: Optional[Decimal]
) -> Optional[Decimal]:
    """
    Calculate percentage change between two prices

    Args:
        old_price: Previous price
        new_price: Current price

    Returns:
        Percentage change, or None if calculation not possible

    Example:
        >>> calculate_price_change_percent(Decimal('10'), Decimal('15'))
        Decimal('50.0')
    """
    if old_price is None or new_price is None:
        return None

    if old_price == 0:
        return None

    change = ((new_price - old_price) / old_price) * Decimal("100")
    return change
