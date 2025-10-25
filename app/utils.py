"""Utility functions"""

import yaml
from pathlib import Path
from typing import Dict, Any
import structlog

logger = structlog.get_logger(__name__)


def load_yaml_config(filepath: str) -> Dict[str, Any]:
    """
    Load YAML configuration file

    Args:
        filepath: Path to YAML file

    Returns:
        Parsed YAML as dictionary
    """
    try:
        path = Path(filepath)
        if not path.exists():
            logger.warning("yaml_file_not_found", filepath=filepath)
            return {}

        with open(path, "r") as f:
            data = yaml.safe_load(f)
            logger.info("yaml_config_loaded", filepath=filepath)
            return data or {}

    except Exception as e:
        logger.error("failed_to_load_yaml", filepath=filepath, error=str(e))
        return {}


def load_provider_config() -> Dict[str, Any]:
    """Load provider configuration from YAML"""
    return load_yaml_config("configs/providers.yml")


def load_blocklist() -> list[str]:
    """Load model blocklist from YAML"""
    config = load_yaml_config("configs/models_blocklist.yml")
    return config.get("blocklist", [])


def is_model_blocked(model_slug: str) -> bool:
    """Check if a model is on the blocklist"""
    blocklist = load_blocklist()
    return model_slug in blocklist
