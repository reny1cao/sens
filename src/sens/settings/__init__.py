"""Settings management for the Sens project.

This package provides configuration management through environment variables
with validation using Pydantic models.

Example:
    from sens.settings import get_settings

    settings = get_settings()
    model_name = settings.get_model_for("sql_generator")
"""

from .core import Settings, get_llm_settings, get_settings, reload_settings
from .models import (
    DatabaseConfig,
    EnvironmentType,
    IntentExtractorConfig,
    ModelConfig,
    OpenRouterConfig,
    SQLGeneratorConfig,
)

__all__ = [
    # Core
    "Settings",
    "get_settings",
    "get_llm_settings",
    "reload_settings",
    # Models
    "EnvironmentType",
    "OpenRouterConfig",
    "ModelConfig",
    "SQLGeneratorConfig",
    "IntentExtractorConfig",
    "DatabaseConfig",
]
