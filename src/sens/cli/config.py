"""CLI configuration settings.

This module provides CLI-specific configuration settings that can be controlled
via environment variables or configuration files.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from sens.settings import get_settings as get_base_settings


class CLISettings(BaseSettings):
    """CLI-specific settings."""

    model_config = SettingsConfigDict(
        env_prefix="SENS_CLI_",
        case_sensitive=False,
        extra="ignore",
    )

    # Debug settings
    debug_mode: bool = Field(
        default=False,
        description="Enable debug mode for detailed output",
    )
    trace_enabled: bool = Field(
        default=False,
        description="Enable trace-level logging",
    )

    # Metrics settings
    metrics_enabled: bool = Field(
        default=False,
        description="Enable metrics collection and display",
    )
    metrics_history_size: int = Field(
        default=100,
        description="Number of historical metrics entries to keep",
    )

    # Output settings
    default_format: str = Field(
        default="json",
        description="Default output format (json, table, or summary)",
    )
    max_preview_rows: int = Field(
        default=5,
        description="Maximum number of preview rows to show",
    )
    pretty_print: bool = Field(
        default=True,
        description="Enable pretty printing for output",
    )

    # History settings
    history_enabled: bool = Field(
        default=True,
        description="Enable conversation history",
    )
    history_file: Path = Field(
        default=Path.home() / ".sens" / "history.json",
        description="Path to conversation history file",
    )
    max_history_size: int = Field(
        default=1000,
        description="Maximum number of historical entries to keep",
    )

    # Cache settings
    cache_enabled: bool = Field(
        default=True,
        description="Enable caching of results",
    )
    cache_dir: Path = Field(
        default=Path.home() / ".sens" / "cache",
        description="Directory for cached data",
    )
    cache_ttl: int = Field(
        default=3600,
        description="Cache TTL in seconds",
    )

    def model_dump(self, exclude_secrets: bool = False) -> dict:
        """Convert settings to dictionary.

        Args:
            exclude_secrets: Whether to exclude sensitive fields

        Returns:
            Dictionary representation of settings
        """
        data = super().model_dump()
        # Convert Path objects to strings
        for key, value in data.items():
            if isinstance(value, Path):
                data[key] = str(value)
        return data


_cli_settings_instance: Optional[CLISettings] = None


def get_cli_settings() -> CLISettings:
    """Get CLI settings instance.

    Returns:
        CLISettings instance
    """
    global _cli_settings_instance
    if _cli_settings_instance is None:
        _cli_settings_instance = CLISettings()
    return _cli_settings_instance


class EnhancedSettings:
    """Enhanced settings combining base and CLI settings."""

    def __init__(self):
        """Initialize enhanced settings."""
        self.base = get_base_settings()
        self.cli = get_cli_settings()

    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        # Create CLI directories
        self.cli.history_file.parent.mkdir(parents=True, exist_ok=True)
        self.cli.cache_dir.mkdir(parents=True, exist_ok=True)

        # Create base directories
        self.base.index_dir.mkdir(parents=True, exist_ok=True)
        self.base.schema_path.parent.mkdir(parents=True, exist_ok=True)

    def model_dump(self, exclude_secrets: bool = False) -> dict:
        """Convert all settings to dictionary.

        Args:
            exclude_secrets: Whether to exclude sensitive fields

        Returns:
            Dictionary representation of all settings
        """
        return {
            "base": self.base.model_dump(exclude_secrets=exclude_secrets),
            "cli": self.cli.model_dump(exclude_secrets=exclude_secrets),
        }


_enhanced_settings_instance: Optional[EnhancedSettings] = None


def get_enhanced_settings() -> EnhancedSettings:
    """Get enhanced settings instance.

    Returns:
        EnhancedSettings instance
    """
    global _enhanced_settings_instance
    if _enhanced_settings_instance is None:
        _enhanced_settings_instance = EnhancedSettings()
        _enhanced_settings_instance.ensure_directories()
    return _enhanced_settings_instance
